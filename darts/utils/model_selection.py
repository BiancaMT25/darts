from typing import Sequence, Optional, Union, Tuple
from ..timeseries import TimeSeries


class SplitTimeSeriesSequence(Sequence):
    """
    This class is primarily meant to be instantiated from ``train_test_split()`` function.
    """
    def __init__(self,
                 type: str,
                 data: Union[TimeSeries, Sequence[TimeSeries]],
                 test_size: Optional[Union[float, int]] = 0.25,
                 axis: Optional[int] = 0,
                 input_size: Optional[int] = 0,
                 horizon: Optional[int] = 0,
                 vertical_split_type: Optional[str] = 'simple'):

        if type not in ['train', 'test']:
            raise AttributeError('Value for type parameter should be either `train` or `test`')

        if not data:
            raise AttributeError('The `data` parameter cannot be empty.')

        if axis not in [0, 1]:
            raise AttributeError('The `axis` parameter should be either 0 or 1.')

        if axis == 1 and vertical_split_type == 'model-aware' and (horizon == 0 or input_size == 0):
                raise AttributeError("You need to provide non-zero `horizon` and `input_size` parameters when axis=1")

        if vertical_split_type not in ['simple', 'model-aware']:
            raise AttributeError('`vertical_split_type` can be eiter `simple` or `model-aware`.')

        self.type = type
        self.data = data
        self.test_size = test_size
        self.axis = axis
        self.input_size = input_size
        self.horizon = horizon
        self.vertical_split_type = vertical_split_type

    def _get_horizontal_split_index(self):
        if 0 < self.test_size < 1:
            return int(len(self.data) * (1 - self.test_size))
        else:
            return len(self.data) - self.test_size

    def _get_vertical_split_indices(self, ts_length):

        if self.vertical_split_type == 'simple':
            if 0 < self.test_size < 1:
                test_size = int(ts_length * self.test_size)
            else:
                test_size = self.test_size

            test_start_index = ts_length - test_size
            train_end_index = test_start_index

            if test_start_index < 0:
                raise AttributeError("`test_size` is bigger then timeseries length")

        else: # model-aware split
            train_end_index = ts_length - self.horizon

            if 0 < self.test_size < 1:
                test_size = int((ts_length - self.horizon) * (self.test_size))
            else:
                test_size = self.test_size

            if train_end_index < 0:
                train_end_index = 0

            if train_end_index < self.input_size:
                raise AttributeError("Training timeseries is of 0 size")

            test_start_index = ts_length - self.horizon - self.input_size - test_size - 1

            if test_start_index < 0:
                raise AttributeError("Not enough timesteps to create testset")

        return train_end_index, test_start_index

    def __getitem__(self, i: int) -> TimeSeries:
        if self.axis == 0:
            split_index = self._get_horizontal_split_index()
            if self.type == 'train':
                if i >= split_index:
                    raise IndexError('Exceeded the size of the training sequence.')
                return self.data[i]
            else:
                if i + split_index > len(self.data):
                    raise IndexError('Exceeded the size of the test sequence.')
                return self.data[split_index + i]
        else: # axis == 1
            train_end_index, test_start_index = self._get_vertical_split_indices(len(self.data[i]))
            if self.type == 'train':
                return self.data[i][:train_end_index]
            else:
                return self.data[i][test_start_index:]

    def __len__(self):
        if self.axis == 0:
            split_index = self._get_horizontal_split_index()
            if self.type == 'train':
                return split_index
            else:
                return len(self.data) - split_index
        else:
            return len(self.data)

    @classmethod
    def make_splitter(cls,
                      data: Union[TimeSeries, Sequence[TimeSeries]],
                      test_size: Optional[Union[float, int]] = 0.25,
                      axis: Optional[int] = 0,
                      input_size: Optional[int] = 0,
                      horizon: Optional[int] = 0,
                      vertical_split_type: Optional[str] = 'simple',
                      lazy: bool = False
                      ) -> Union[Tuple[TimeSeries, TimeSeries], Tuple[Sequence[TimeSeries], Sequence[TimeSeries]]]:

        if not isinstance(data, Sequence):
            axis = 1
            data = [data]  # convert to sequence for unified processing later
            single_timeseries = True
        else:
            single_timeseries = False

        train_set = cls(type='train', data=data, test_size=test_size, axis=axis, input_size=input_size, horizon=horizon,
                        vertical_split_type=vertical_split_type)

        test_set = cls(type='test', data=data, test_size=test_size, axis=axis, input_size=input_size, horizon=horizon,
                       vertical_split_type=vertical_split_type)

        if single_timeseries:
            return train_set[0], test_set[0]
        else:
            if lazy:
                return train_set, test_set
            else:
                return list(train_set), list(test_set)


def train_test_split(
        data: Union[TimeSeries, Sequence[TimeSeries]],
        test_size: Optional[Union[float, int]] = 0.25,
        axis: Optional[int] = 0,
        input_size: Optional[int] = 0,
        horizon: Optional[int] = 0,
        vertical_split_type: Optional[str] = 'simple',
        lazy: bool = False
        ) -> Union[Tuple[TimeSeries, TimeSeries], Tuple[Sequence[TimeSeries], Sequence[TimeSeries]]]:
    """
    Splits the dataset into training and test dataset. Supports splitting along the sample axis and time axis.

    If the input type is single TimeSeries, then only splitting over time axis is available, thus ``n`` and ``horizon``
    have to be provided.

    When splitting over the time axis, splitter tries to greedy satisfy the requested test set size, i.e. when one of
    the timeseries in sequence is too small, all samples will go to the test set and the warning will be issued.

    Parameters
    ----------
    data
        original dataset to split into training and test

    test_size
        size of the test set. If the value is between 0 and 1, parameter is treated as a split proportion. Otherwise
        it is treated as a absolute number of samples from each timeseries that will be in the test set. [default = 0.25]

    axis
        Axis to split the dataset on. When 0 (default) it is split on samples. Otherwise, if ``axis = 1``,
        timeseries are split along time axis. Note that for single timeseries the default option is 1 (0 makes
        no sense). [default: 0 for sequence of timeseries, 1 for timeseries]

    input_size
        size of the input [default: 0]

    horizon
        forecast horizon [default: 0]

    vertical_split_type
        can be either ``simple``, where the exact number from test size will be deducted from timeseries for test set and
        remaining will go to training set; or ``model-aware``, where you have to provide ``input_size`` and ``horizon``
        as well. Note, that second option is more efficient timestep-wise, since training and test sets will be
        partially overlapping. [default: ``simple``]

    lazy
        by default, train and test datasets are returned as a list of timeseries. This may be memory
        inefficient if dataset is large, so setting this flag allows instead to return a ``Sequence`` object
        loading the data lazily. Warning: turning ``lazy`` on disables some sanity checks for the datasets
        that may result in exceptions during sample generation. [default: False]

    Returns
    -------
    tuple of two Sequence[TimeSeries], or tuple of two Timeseries
        Training and test datasets tuple.
    """

    return SplitTimeSeriesSequence.make_splitter(data, test_size, axis, input_size, horizon, vertical_split_type, lazy)
