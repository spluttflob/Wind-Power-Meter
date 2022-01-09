"""!
@file turboplot.py
    This file contains a program which makes simple plots of wind
    turbine generation.

@author JR Ridgely
@date   2021-Jun-08 JRR Original file
@date   2022-Jan-08 JRR Updates to documentation for repository
"""

import io
import time
from smbus import SMBus
import PySimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasAgg
from matplotlib import figure, pyplot
from turbo_hat import TurboHAT


def create_plots(times, data, xlabel=None, ylabels=None,
                 plot_titles=None, title=None):
    """!
    Create a plot or plots with the given time array and list of data arrays.
    @param times An iterable of time axis coordinates
    @param data A list of iterables of vertical axis coordinates
    @param xlabel The label for the plot X axes
    @param ylabels An iterable of labels for plot Y axes
    @param plot_titles An iterable of titles of plots
    @param title An overall title for Life, the Universe, and Everything
    @returns A list of figures, one for each plot
    """
    pyplot.style.use("dark_background")

    # Figure out how many plots' worth of data are present and set
    # up that many subplots; for each subplot there may be more than
    # one series of data
    num_plots = len(data)

    figures = []

    for subplot_num in range(num_plots):
        fig = figure.Figure(figsize=(5, 4), dpi=100)
#         subplot_code = num_plots * 100 + 10 + (subplot_num + 1)
        axis = fig.add_subplot(111) ####### subplot_code)

        # Plot each of the series on this plot. Serieses?
        for series in data[subplot_num]:
            oneline = axis.plot(times, series)
        if xlabel:
            axis.set_xlabel (xlabel)
        if ylabels:
            axis.set_ylabel (ylabels[subplot_num])
        if plot_titles:
            axis.set_title (plot_titles[subplot_num])
#         if title:
#             fig.suptitle(title)
        figures.append(fig)

    return figures


def draw_figures(figures, elements):
    """!
    Draw the plots which have been created in create_plots().
    @param figures A list of figures containing the plots
    @param elements The screen elements on which the plots are drawn
    """
    for fig, elle in zip(figures, elements):
        canv = FigureCanvasAgg(fig)
        buf = io.BytesIO()
        canv.print_figure(buf, format='png')

        if buf is not None:
            buf.seek(0)
            data = buf.read()
            elle.update(data=data)


def print_data(times, data):
    """!
    This function prints (or displays) a set of turbine data.
    @param times A list of times
    @param data The list of lists of lists holding the data
    """
    for index in range(len(times)):
        print ("{:.3f},".format (times[index]), end='')
        for plot in data:
            for channel in plot:
                print ("{:.2f},".format (channel[index]), end='')
        print ("")


def main():
    """!
    Run the program.
    """
    data_period = 1.0              # Time between data acquisitions in seconds
    start_time = time.time()       # Save starting time for relative timing
    next_data_time = 0.0           # Time to take the next data point

    # Set up the power measurement hardware
    i2c_bus = SMBus (1)
    turbo = TurboHAT (i2c_bus, i2c_address=0x40, reset_pin=12, drdy_pin=16)

    # Create some arrays (well, lists) for time and voltage data. Times
    # are a simple array. Data is arranged as an array of subplots, each
    # of which contains a list of channels. Variables 'data', 'channels',
    # and 'legends' must have matching dimensions
    times = []
    data = [[[], []], [[], []]]
    channels = [[0, 2], [1, 3]]
    legends = [['Turbine 1 Voltage', 'Turbine 1 Current'],
               ['Turbine 2 Voltage', 'Turbine 2 Current']]
    x_label = "Time (s)"
    y_labels = ["Ch 0,2 V", "Ch 1,3 V"]          # One per subplot
    plot_titles = ["Turbine 1", "Turbine 2"]
    plots_title = "Wind Turbine Power"

    # Specify calibration for each ADC channel; this flat list just
    # gives numbers for channels 0 through 3 in order
    calibrations = [5.0 / 32768, 5.0 / 32768, 5.0 / 32768, 5.0 / 32768]

    # Make a flat list of channels and a set of columns for printing 'em.
    # The columns must be in a list of lists of lists. Really
    flat_channels = [item for sublist in channels for item in sublist]
    chan_labs = [[[sg.Text("Ch. {:d}".format(num), size=(16, 1),
                           font=("Helvetica", 12), justification="center")
                   for num in flat_channels]]]
    chan_cols = [[[sg.Text(key="-CH{:d}-".format(num), size=(16, 1),
                           font=("Helvetica", 12), justification="center")
                   for num in flat_channels]]]

    # Choose a theme for the plots, or don't for the boring default
    sg.theme ("DarkGrey5")

    # ------------------------------------------------------------------------
    # Set up the screen layout and main window

    # Indicators for the readings from the channels
    layout = [[[sg.Column(col) for col in chan_labs]],
              [[sg.Column(col) for col in chan_cols]]]

    # The place where the plots will go
    layout.append([[sg.Image(key="-PLOT{:d}-".format(plot_num))
                  for plot_num in range(len(data))]])

    # A row of control buttons
    layout.append([[sg.Button("Clear"),
                    sg.Button("Save Plots"),
                    sg.Button("Save Data"),
                    sg.Button("Exit")]])

    window = sg.Window("Turbine Power", layout)

    # Make a list of plot windows; it's used when drawing plots onscreen
    plot_windows = [window['-PLOT{:d}-'.format(x)] for x in range(len(data))]

    # ------------------------------------------------------------------------
    # Run the event loop with a timer so data is read every second
    while True:
        event, values = window.read(timeout=1000)

        # If the program is exiting, break out of the event loop
        if event == 'Exit' or event == sg.WIN_CLOSED:
            break

        # If the 'Clear' button was pressed, empty the data arrays
        # except for the most recent point(s)
        if event == 'Clear':
            try:
                del times[:-1]
                for subplot in data:
                    for oneplot in subplot:
                        del oneplot[:-1]
            except IndexError:
                print ("Attempt to clear empty data arrays")
                pass

        # If the 'Save Data' button was pressed, do it
        if event == "Save Data":
            print_data(times, data)

        else:
            # Check that it's time to acquire some more data
            now_time = time.time() - start_time
            if now_time > next_data_time:
                next_data_time += data_period

                # Presumably this means the timer has gone off; get
                # data and plot it
                times.append(time.time() - start_time)
                for subplot in range(len(data)):
                    for chan in range(len(data[subplot])):
                        # For each channel, read data, calibrate and save
                        channel_number = (channels[subplot])[chan]
                        channel_data = turbo.read_channel(channel_number)
                        channel_data *= calibrations[channel_number]
                        (data[subplot])[chan].append(channel_data)
                        # Also update the channel reading boxes
                        window["-CH{:d}-".format(channel_number)].update(
                            "{:.3f}".format(channel_data))

                draw_figures(create_plots(times, data,
                                          xlabel=x_label,
                                          ylabels=y_labels,
                                          title=plots_title,
                                          plot_titles=plot_titles),
                             plot_windows)

    # Clean things up when exiting the program
    turbo.clean_up()
    window.close()
    

if __name__ == "__main__":
    main()


