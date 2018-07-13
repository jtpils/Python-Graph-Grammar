#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import wx
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
from functools import wraps
from typing import TypeVar, Dict, Tuple, MutableSequence
from collections import deque
from graph import Graph
from productions import Production
from utils import Bidict
import test1

T = TypeVar('T')


class GraphUI(wx.Frame):
    """
    The main window of the Application.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_menus()
        self.panel = wx.Panel(self)
        self.notebook = MainNotebook(self.panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, proportion=1, flag=wx.ALL | wx.EXPAND)
        self.panel.SetSizer(sizer)
        self.Layout()
        self.Show()

        self.host_graphs: Dict[str, Graph] = {}
        self.productions: Dict[str, Production] = {}
        self.result_graphs: Dict[str, Graph] = {}

    def setup_menus(self) -> None:
        """
        Add all menu items to the wx window.
        """
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_quit = file_menu.Append(wx.ID_EXIT, item='Quit', helpString='Quit Model Gen')
        menubar.Append(file_menu, title='&File')
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_quit, file_quit)

    def load_graphs(self, host_graphs: Dict[str, Graph], productions: Dict[str, Production],
                    result_graphs: Dict[str, Graph]) -> None:
        self.host_graphs = host_graphs
        self.productions = productions
        self.result_graphs = result_graphs
        self.notebook.host_graph_panel.load_data(self.host_graphs)
        self.notebook.result_panel.load_data(self.result_graphs)

    def on_quit(self, _) -> None:
        self.Close()


class MainNotebook(wx.Notebook):
    """
    The notebook containing the three main tabs of the UI.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host_graph_panel = HostGraphPanel(self)
        self.production_panel = GraphPanel(self)
        self.result_panel = ResultGraphPanel(self)
        self.AddPage(self.host_graph_panel, 'Host Graphs')
        self.AddPage(self.production_panel, 'Productions')
        self.AddPage(self.result_panel, 'Result Graphs')


class HostGraphPanel(wx.Panel):
    """
    Container used to display and edit host graphs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.list.InsertColumn(0, 'name', width=150)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select)
        self.graph_panel = GraphPanel(self)
        hbox.Add(self.list, proportion=0, flag=wx.EXPAND)
        hbox.Add(self.graph_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)

        self.host_graphs: Dict[int, Tuple[str, Graph]] = {}

    def load_data(self, data: Dict[str, Graph]) -> None:
        """
        Load new data into the host graph displays.

        :param data: The host graphs to load
        """
        i = 0
        for name, graph in data.items():
            index = self.list.InsertItem(i, name)
            self.host_graphs[index] = (name, graph)
            i += 1

    def on_select(self, event) -> None:
        item_index = event.GetIndex()
        graph = self.host_graphs[item_index][1]
        self.graph_panel.load_graph(graph)


class ResultGraphPanel(wx.Panel):
    """
    Container used to display result graphs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.list = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.list.InsertColumn(0, 'name', width=150)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select)
        self.graph_panel = GraphPanel(self)
        hbox.Add(self.list, proportion=0, flag=wx.EXPAND)
        hbox.Add(self.graph_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)

        self.result_graphs: Dict[int, Tuple[str, Graph]] = {}

    def load_data(self, data: Dict[str, Graph]) -> None:
        """
        Load new data into the host graph displays.

        :param data: The host graphs to load
        """
        i = 0
        for name, graph in data.items():
            index = self.list.InsertItem(i, name)
            self.result_graphs[index] = (name, graph)
            i += 1

    def on_select(self, event) -> None:
        item_index = event.GetIndex()
        graph = self.result_graphs[item_index][1]
        self.graph_panel.load_graph(graph)


class GraphPanel(wx.Panel):
    """
    A container for the plots of a graph.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # matplotlib objects
        self.figure = Figure(figsize=(2, 2))
        self.figure.patch.set_facecolor('white')
        self.subplot = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, id=wx.ID_ANY, figure=self.figure)
        self.toolbar = NavigationToolbar(canvas=self.canvas)
        self.toolbar.Realize()
        # wxpython layout elements
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, proportion=1, flag=wx.EXPAND)
        sizer.Add(self.toolbar, proportion=0, flag=wx.LEFT | wx.EXPAND)

        self.SetSizer(sizer)
        # Other Stuff
        self.setup_mpl_visuals()
        self.canvas.Show()

        on_press_cid = self.canvas.mpl_connect('button_press_event', self.on_press)
        on_release_cid = self.canvas.mpl_connect('button_release_event', self.on_release)
        on_pick_cid = self.canvas.mpl_connect('pick_event', self.on_pick)
        on_hover_cid = self.canvas.mpl_connect('motion_notify_event', self.on_move)

        self.points = [(0, 0), (1, 1), (3, 1), (-2, -2)]
        self.circles = Bidict()
        self.lines = Bidict()
        self.graph = None

    def setup_mpl_visuals(self) -> None:
        """
        Setup all the visual setting of the matplotlib canvas, figure and subplot.

        This function needs to be called every time the mpl figure is redrawn because
        clearing the figure allso resets all these visual settings.
        """
        self.subplot.patch.set_facecolor('white')
        self.subplot.set_xlim(-10, 10, auto=True)
        self.subplot.set_ylim(-10, 10, auto=True)
        # TODO: Make XYLim confort to window size/dimensions
        self.subplot.set_xticks([])
        self.subplot.set_yticks([])
        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)
        self.subplot.axis('off')

    def redraw(self) -> None:
        """
        Call all update function necessary to update the graph visualisation.
        """
        self.canvas.draw()
        self.Refresh()

    def _is_update(f: T) -> T:
        """
        A decorator to wrap a function performing visual updates with all necessary
        housekeeping functions.
        """

        @wraps(f)
        def wrap(self, *args, **kwargs) -> T:
            # Before update operations
            self.subplot.clear()
            # Update Function
            result = f(self, *args, **kwargs)
            # After update operations
            self.setup_mpl_visuals()
            self.redraw()
            return result

        return wrap

    @_is_update
    def draw_line(self) -> None:
        """
        Draw a line connecting all points in self.points.
        """
        self.subplot.plot([x for x, _ in self.points], [y for _, y in self.points], picker=100)

    @_is_update
    def draw_points(self) -> None:
        """
        Draw all points in self.points as individual circles.
        """
        for point in self.points:
            self.circles.append(DraggableCircle(point, 0.5, update_func=self.redraw, color='w', ec='k'))
        for circle in self.circles:
            self.subplot.add_artist(circle)
            circle.register_events()

    @_is_update
    def draw_graph(self) -> None:
        """
        Draw the graph as a set of circles and connecting edges.
        """

        def add_new_free_spaces(pos: Tuple[int, int], free_spaces: MutableSequence[Tuple[int, int]]) -> None:
            """
            Add newly available free spaces adjacent to pos to the list if they are not already present.

            :param pos: The position adjacent to which new spaces will be searched.
            :param free_spaces: The list to which new free spaces will be added
            """
            possible_positions = [
                (pos[0] + 1, pos[1] + 1),
                (pos[0] + 1, pos[1]),
                (pos[0] + 1, pos[1] - 1),
                (pos[0], pos[1] - 1),
                (pos[0] - 1, pos[1] - 1),
                (pos[0] - 1, pos[1]),
                (pos[0] - 1, pos[1] + 1),
                (pos[0], pos[1] + 1)
            ]
            for candidate in possible_positions:
                if candidate not in free_spaces:
                    free_spaces.append(candidate)

        i = 0
        free_spaces = [(0, 0)]
        for vertex in self.graph.vertices:
            position = free_spaces[i]
            add_new_free_spaces(position, free_spaces)
            circle = DraggableCircle(position, 0.5, update_func=self.redraw, label_func=self.get_vertex_desc, color='w', ec='k', zorder=10)
            self.circles[vertex] = circle
            self.subplot.add_artist(circle)
            circle.register_events()
            i += 1
        for edge in self.graph.edges:
            pos1 = self.circles[edge.vertex1].center
            pos2 = self.circles[edge.vertex2].center
            line = plt.Line2D((pos1[0], pos2[0]), (pos1[1], pos2[1]), c='k')
            self.lines[edge] = line
            self.subplot.add_artist(line)

    def load_graph(self, graph: Graph) -> None:
        """
        Load and display the passed graph.

        :param graph: The graph to be displayed
        """
        self.graph = graph
        self.circles = Bidict()
        self.draw_graph()

    def get_vertex_desc(self, circle: plt.Circle) -> str:
        """
        Get a textual description of the attributes of the vertex corresponding to the circle passed as argument.

        :param circle: The circle to which the corresponding description is requested.
        :return: The description of the corresponding vertex
        """
        vertex = self.circles.inverse[circle][0]
        text = ''
        for name, value in vertex.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    def on_press(self, event):
        print(f'button={event.button}, x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}')
        pass

    def on_release(self, event):
        pass

    def on_pick(self, event):
        print(f'Pick event.')

    def on_move(self, event):
        pass


class DraggableCircle(plt.Circle):
    def __init__(self, *args, update_func=None, label_func=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_func = update_func
        self.label_func = label_func
        self.annotation = None
        self.pressed = False
        self.hovered = False
        self.start_circ_pos = None
        self.start_mouse_pos = None
        self.on_press_cid = None
        self.on_release_cid = None
        self.on_hover_cid = None

    def register_events(self):
        self.on_press_cid = self.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.on_release_cid = self.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.on_hover_cid = self.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        if self.contains(event)[0]:
            self.pressed = True
            self.start_circ_pos = self.center
            self.start_mouse_pos = (event.xdata, event.ydata)
            self.set_facecolor('red')
            self.update_func()

    def on_release(self, event):
        if self.pressed:
            self.pressed = False
            self.start_circ_pos = None
            self.start_mouse_pos = None
            self.set_facecolor('white')
            self.update_func()

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return
        if self.pressed:
            dx = event.xdata - self.start_mouse_pos[0]
            dy = event.ydata - self.start_mouse_pos[1]
            self.center = (self.start_circ_pos[0] + dx, self.start_circ_pos[1] + dy)
            self.update_func()
        if self.contains(event)[0]:
            if not self.hovered:
                self.hovered = True
                if self.annotation is None:
                    axis = self.figure.gca()
                    text = self.label_func(self)
                    self.annotation = axis.annotate(text,
                                                    xy=self.center,
                                                    xytext=(10, 10),
                                                    textcoords='offset pixels',
                                                    arrowprops=dict(arrowstyle='->'),
                                                    bbox=dict(boxstyle='round', fc='w'),
                                                    zorder=20)
                self.annotation.set_visible(True)
                self.update_func()
        else:
            if self.hovered:
                self.hovered = False
                if self.annotation is not None:
                    self.annotation.set_visible(False)
                    self.update_func()


data = (['name1'], ['name2'])
app = wx.App()
main_frame = GraphUI(None, title="Model Gen Graph Grammar", size=(600, 400))
main_frame.load_graphs(test1.host_graphs, test1.productions, test1.result_graphs)
# plot = GraphPanel(main_frame)
# plot.load_data(data)
# main_frame.Show()
app.MainLoop()
