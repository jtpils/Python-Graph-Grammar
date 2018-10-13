import abc
from typing import Dict, Tuple, Set, MutableSequence

import wx
from matplotlib import pyplot as plt
from matplotlib.backends.backend_wx import \
    NavigationToolbar2Wx as NavigationToolbar
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import ConnectionPatch
import matplotlib.patheffects as pe
import matplotlib.backend_bases
from pydispatch import dispatcher

from exceptions import ModelGenArgumentError
from graph import GraphElement, Graph, Vertex, Edge
from utils import Bidict, Mapping, get_logger
from model_gen.opts import Opts

log = get_logger('model_gen.' + __name__)
opts = Opts()


class GraphPanel(wx.Panel):
    """
    A container for the plots of a graph.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # matplotlib objects
        self.figure = Figure(figsize=(2, 2))
        self.figure.patch.set_facecolor('white')
        self.subplot = self.figure.add_subplot(111)  # Is of type Axes
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

        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.canvas.mpl_connect('key_release_event', self.on_key_release)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)

        self.pressed_elements: Dict[FigureElement, Tuple[float, float]] = {}
        self.press_start_position: Tuple[float, float] = None
        self.pressed_keys: Dict[str, bool] = {}
        self.selected_element: FigureElement = None

        self.graph: Graph = None
        self.graph_to_figure: Bidict[GraphElement, FigureElement] = Bidict()
        self.vertices: Set[FigureVertex] = set()
        self.edges: Set[FigureEdge] = set()

    @property
    def elements(self) -> Set['FigureElement']:
        return self.vertices | self.edges

    def setup_mpl_visuals(self, axes=None) -> None:
        """
        Setup all the visual setting of the matplotlib canvas, figure
        and subplot.

        This function needs to be called every time the mpl figure is
        redrawn because clearing the figure allso resets all these
        visual settings.

        :param axes: The axes for which the visuals shall be set.
        """
        if axes is None:
            axes = self.subplot
        axes.patch.set_facecolor('white')
        axes.set_xlim(-10, 10, auto=True)
        axes.set_ylim(-10, 10, auto=True)
        # TODO: Make XYLim confort to window size/dimensions
        axes.set_xticks([])
        axes.set_yticks([])
        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)
        axes.axis('off')

    def redraw(self) -> None:
        """
        Call all update function necessary to update the graph visualisation.
        """
        self.canvas.draw_idle()
        self.Refresh()

    def draw_graph(self, graph=None, axes=None) -> None:
        """
        Draw the graph as a set of circles and connecting edges.
        """

        # noinspection PyShadowingNames
        def add_new_free_spaces(pos: Tuple[int, int],
                                free_spaces: MutableSequence[
                                    Tuple[int, int]]) -> None:
            """
            Add newly available free spaces adjacent to pos to the
            list if they are not already present.

            :param pos: The position adjacent to which new spaces
                        will be searched.
            :param free_spaces: The list to which new free spaces
                                will be added
            """
            offset = 2
            possible_positions = [
                (pos[0] + offset, pos[1] + offset),
                (pos[0] + offset, pos[1]),
                (pos[0] + offset, pos[1] - offset),
                (pos[0], pos[1] - offset),
                (pos[0] - offset, pos[1] - offset),
                (pos[0] - offset, pos[1]),
                (pos[0] - offset, pos[1] + offset),
                (pos[0], pos[1] + offset)
            ]
            for candidate in possible_positions:
                if candidate not in free_spaces:
                    free_spaces.append(candidate)

        if axes is None:
            axes = self.subplot
        if graph is None:
            graph = self.graph
        i = 0
        free_spaces = [(0, 0)]
        for graph_vertex in graph.vertices:
            position = free_spaces[i]
            add_new_free_spaces(position, free_spaces)
            figure_vertex = FigureVertex(graph_vertex, position, 0.5,
                                         color='w', ec='k', zorder=10)
            self.vertices.add(figure_vertex)
            self.graph_to_figure[graph_vertex] = figure_vertex
            axes.add_artist(figure_vertex)
            i += 1
        for graph_edge in graph.edges:
            figure_vertex1 = self.graph_to_figure[graph_edge.vertex1]
            figure_vertex2 = self.graph_to_figure[graph_edge.vertex2]
            figure_edge = FigureEdge(graph_edge, vertex1=figure_vertex1,
                                     vertex2=figure_vertex2, c='k')
            self.edges.add(figure_edge)
            self.graph_to_figure[graph_edge] = figure_edge
            axes.add_artist(figure_edge)
        if opts['show_all_labels']:
            for element in self.elements:
                if element.get_hover_text() != '':
                    element.annotation = self.annotate_element(element)
        self.setup_mpl_visuals(axes)
        self.redraw()

    def annotate(self, text: str, position: Tuple[int, int],
                 axes: plt.Axes = None) -> plt.Annotation:
        """
        Places an annotation on the subplot.

        :param text: The text to place.
        :param position: The positon of the annotation.
        :param axes: The axes to add the annotation to
        :return: The Annotation object representing the annotation.
        """
        if axes is None:
            axes = self.subplot
        annotation = axes.annotate(text,
                                   xy=position,
                                   xytext=(10, 10),
                                   textcoords='offset pixels',
                                   arrowprops=dict(
                                       arrowstyle='->'),
                                   bbox=dict(
                                       boxstyle='round',
                                       fc='w'),
                                   zorder=20)
        annotation.set_visible(True)
        return annotation

    def annotate_element(self, element: 'FigureElement') -> plt.Annotation:
        """
        Annotate a FigureElement.

        This is a convenience function so you don't need to pass all
        three arguments separately, they are all taken from the
        passed element.

        :param element: The FigureElement to annotate
        :return: The Annotation object representing the annotation.
        """
        return self.annotate(element.get_hover_text(),
                             element.get_center(),
                             element.axes)

    def _clear_drawing(self) -> None:
        """
        Clears the current drawing and dicts/lists referencing the
        drawn elements.
        """
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()

    def _redraw_graph(self) -> None:
        """
        Redraw the currently loaded graph.
        """
        self._clear_drawing()
        self.draw_graph()

    def load_graph(self, graph: Graph) -> None:
        """
        Load and display the passed graph.

        :param graph: The graph to be displayed
        """
        self.graph = graph
        self._redraw_graph()

    def _get_connected_graph(self, axes: plt.Axes) -> Graph:
        """
        Return the graph that is represented by the specified axes.

        :param axes: Axes to which the corresponding graph is to be
            found.
        :return: Graph represented by the Axes.
        """
        if axes == self.subplot:
            return self.graph
        else:
            raise KeyError('Specified Axes could not be found.')

    def add_vertex(self, event: matplotlib.backend_bases.LocationEvent) \
            -> None:
        """
        Adds a vertex to the graph at the position defined by the mpl event.

        :param event: The matplotlib event that initiated the adding.
        """
        log.info(f'Adding Vertex @ {event.x} - {event.y}')
        graph = self._get_connected_graph(event.inaxes)
        vertex = Vertex()
        graph.add(vertex)
        self._redraw_graph()

    def connect_vertices(self, event: matplotlib.backend_bases.LocationEvent,
                         vertex: 'FigureVertex') -> None:
        """
        Adds a new Edge between two vertices, if self.selected_element
        is not None. If it is None then it sets self.selected_element
        to the vertex passed as argument.

        :param event: The event that initiated this action.
        :param vertex: Vertex to connect to another vertex.
        """
        log.debug('connecting Vertices')
        if self.selected_element is None:
            self.selected_element = vertex
            vertex.add_extra_path_effect('selection',
                                         pe.Stroke(linewidth=5,
                                                   foreground='b'))
            return
        graph = self._get_connected_graph(event.inaxes)
        vertex1 = self.graph_to_figure.inverse[self.selected_element][0]
        vertex2 = self.graph_to_figure.inverse[vertex][0]
        new_edge = Edge(vertex1, vertex2)
        graph.add(new_edge)
        self.selected_element.remove_extra_path_effect('selection')
        self.selected_element = None
        self._redraw_graph()

    def delete_element(self, event: matplotlib.backend_bases.LocationEvent) \
            -> None:
        """
        Removes the hovered Elements from the graph.

        :param event: The matplotlib event that initiated the removal.
        """
        log.info(f'Removing Element(s) @ {event.x} - {event.y}')
        graph = self._get_connected_graph(event.inaxes)
        to_remove = {x for x in self.elements if x.contains(event)[0]}
        log.info(f'Elements to remove are {to_remove}')
        for element in to_remove:
            graph.remove(self.graph_to_figure.inverse[element][0])
        self._redraw_graph()

    def event_in_axes(self, event: matplotlib.backend_bases.Event) -> bool:
        """
        Test if an event is inside the axes of this Panel.

        :param event: The event to check.
        :return: True if the event is inside the axes, False otherwise.x
        """
        return event.inaxes == self.subplot

    def on_press(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        if event.button == 1:  # 1 = left click
            self.press_start_position = (event.xdata, event.ydata)
            for element in self.elements:
                if element.contains(event)[0]:
                    self.pressed_elements[element] = element.get_center()
                    dispatcher.connect(receiver=element.on_position_change,
                                       signal='element_position_changed')

    def on_release(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        if event.button == 1:  # 1 = left click
            if event.key == 'ctrl+control':
                self.add_vertex(event)
                return
            self.press_start_position = None
            for element in self.elements:
                if element.contains(event)[0] \
                        and element in self.pressed_elements:
                    self.pressed_elements.pop(element)
                    dispatcher.disconnect(receiver=element.on_position_change,
                                          signal='element_position_changed')
        elif event.button == 3:  # 3 = right click
            for vertex in self.vertices:
                if vertex.contains(event)[0]:
                    self.connect_vertices(event, vertex)
                    return
            if self.selected_element is not None:
                self.selected_element.remove_extra_path_effect('selection')
                self.selected_element = None
            self.redraw()

    def on_key_press(self, event: matplotlib.backend_bases.KeyEvent):
        self.pressed_keys[event.key] = True

    def on_key_release(self, event: matplotlib.backend_bases.KeyEvent):
        if (event.key == 'd' and self.pressed_keys['control']) \
                or event.key == 'delete':
            self.delete_element(event)
        self.pressed_keys[event.key] = False

    def on_pick(self, event: matplotlib.backend_bases.PickEvent):
        pass

    def on_motion(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        for element in self.elements:
            if element.contains(event)[0]:
                if not element.hovered:
                    element.hovered = True
                    element.on_hover()
                    if element.annotation is None \
                            and element.get_hover_text() != '':
                        element.annotation = self.annotate_element(element)
            else:
                if element.hovered:
                    element.hovered = False
                    element.on_unhover()
                    if element.annotation is not None \
                            and not opts['show_all_labels']:
                        element.annotation.set_visible(False)
                        element.annotation.remove()
                        element.annotation = None
        # This is a sanity check. With gui interactions it could easily happen
        # that a mouse release occurs is such a way that an inconsistency
        # appears.
        if len(self.pressed_elements) != 0 \
                and self.press_start_position is None:
            self.pressed_elements.clear()
        elif len(self.pressed_elements) > 0:
            dispatcher.send(signal='element_position_changed', sender=self)
            for element, center in self.pressed_elements.items():
                if isinstance(element, FigureVertex):
                    dx = event.xdata - self.press_start_position[0]
                    dy = event.ydata - self.press_start_position[1]
                    element.center = (center[0] + dx, center[1] + dy)
        self.redraw()


class ProductionGraphsPanel(GraphPanel):
    """
    A container for the plots of two graphs with arrows connecting
    certain elements.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subplot.remove()
        del self.subplot
        self.subplot = self.figure.add_subplot(121)
        self.subplot2 = self.figure.add_subplot(122)
        self.graph2: Graph = None
        self.mapping: Mapping = None
        self.setup_mpl_visuals(self.subplot)
        self.setup_mpl_visuals(self.subplot2)
        self.mappings: Set[ConnectionPatch] = set()

    def _clear_drawing(self) -> None:
        """
        Clears the current drawing and dicts/lists referencing the
        drawn elements.
        """
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()
        self.subplot2.clear()

    def _redraw_graph(self) -> None:
        """
        Redraw the currently loaded graphs.
        """
        self._clear_drawing()
        self.draw_graph(graph=self.graph, axes=self.subplot)
        self.draw_graph(graph=self.graph2, axes=self.subplot2)
        self.draw_mappings(self.mapping)

    def load_graph(self, graph_data: Tuple[Graph, Mapping, Graph]) -> None:
        """
        Load graphs into the two graph displays.

        :param graph_data: The graphs to load
        """
        self.graph = graph_data[0]
        self.graph2 = graph_data[2]
        self.mapping = graph_data[1]
        self._clear_drawing()
        self._redraw_graph()

    def draw_mappings(self, mapping: Mapping) -> None:
        """
        Draw arrows between the GraphElements that are mapped together.

        :param mapping: A Mapping containing the information on what
                        arrows to draw.
        """
        for graph_element1, graph_element2 in mapping.items():
            figure_element1 = self.graph_to_figure[graph_element1]
            figure_element2 = self.graph_to_figure[graph_element2]
            patch = ConnectionPatch(
                xyA=figure_element1.get_center(),
                xyB=figure_element2.get_center(),
                coordsA="data",
                coordsB="data",
                axesA=self.subplot,
                axesB=self.subplot2,
                arrowstyle="->",
                clip_on=False,
            )
            self.mappings.add(patch)
            self.subplot.add_artist(patch)
        self.redraw()

    def _get_connected_graph(self, axes: plt.Axes) -> Graph:
        """
        Return the graph that is represented by the specified axes.

        :param axes: Axes to which the corresponding graph is to be
            found.
        :return: Graph represented by the Axes.
        """
        if axes == self.subplot:
            return self.graph
        elif axes == self.subplot2:
            return self.graph2
        else:
            raise KeyError('Specified Axes could not be found.')

    def event_in_axes(self, event):
        if event.inaxes == self.subplot.axes \
                or event.inaxes == self.subplot2.axes:
            return True
        else:
            return False


class FigureElement(abc.ABC):
    """
    Visual representation of a GraphElement inside a matplotlib figure.

    This is a base class for all other FigureElements to derive from.
    """

    def __init__(self, graph_element: GraphElement):
        self.graph_element = graph_element
        """The GraphElement that is represented by this FigureElement."""
        self.hovered: bool = False
        """Whether or not this element is currently being hovered over."""
        self.annotation: plt.Annotation = None
        """Saves any matplotlib annotation associated with this Element."""
        self.extra_path_effects: Dict[str, pe.AbstractPathEffect] = {}
        """Saves a dict mapping text labels to applied path effects."""

    def get_hover_text(self) -> str:
        """
        Get and return the on-hover text of the element.

        :return: A string containing the hover text of the element.
        """
        text = ''
        for name, value in self.graph_element.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        self.extra_path_effects[name] = effect

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        self.extra_path_effects.pop(name)

    def on_hover(self) -> None:
        """
        Called when the element is hovered.
        """

    def on_unhover(self) -> None:
        """
        Called when an element stops being hovered.
        """

    @abc.abstractmethod
    def get_center(self) -> Tuple[int, int]:
        """
        Return the center position of this element.

        :return: A tuple containing the centers x and y coordinate.
        """
        raise NotImplementedError()

    def on_position_change(self) -> None:
        """
        Is called when the Position of an Element is changed.
        """
        pass


class FigureVertex(FigureElement, plt.Circle):
    """
    The visual representation of a Vertex.
    """

    def __init__(self, graph_element: GraphElement, *args, edges=None,
                 **kwargs):
        FigureElement.__init__(self, graph_element)
        plt.Circle.__init__(self, *args, **kwargs)
        self.edges: Set[FigureEdge] = set() if edges is None else edges
        """A set containing all Edges connected to this Vertex."""
        for edge in self.edges:
            if self not in {edge.vertex1, edge.vertex2}:
                if edge.vertex1 is None:
                    edge.vertex1 = self
                elif edge.vertex2 is None:
                    edge.vertex2 = self
                else:
                    log.error(f'The FigureVertex was passed Edge {edge} as '
                              f'Argument but the Edge is already connected to '
                              f'two other Vertices.')
                    raise ModelGenArgumentError('Edge is already connected to '
                                                'two other Vertices.')

    def get_center(self) -> Tuple[int, int]:
        return self.center

    def update_path_effects(self) -> None:
        """
        Updates the applied path effects.
        """
        effects = list(self.extra_path_effects.values())
        effects.append(pe.Normal())
        self.set_path_effects(effects)

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        super().add_extra_path_effect(name, effect)
        self.update_path_effects()

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        super().remove_extra_path_effect(name)
        self.update_path_effects()

    def on_position_change(self):
        for edge in self.edges:
            edge.update_position()
        if self.annotation is not None:
            self.annotation.xy = self.center

    def on_hover(self):
        log.debug(f'Setting path effect on {self}')
        self.add_extra_path_effect('hover',
                                   pe.Stroke(linewidth=3, foreground='r'))

    def on_unhover(self):
        log.debug(f'Unsetting path effect on {self}')
        self.remove_extra_path_effect('hover')


class FigureEdge(FigureElement, plt.Line2D):
    """
    The visual representation of an Edge.
    """

    def __init__(self, graph_element: GraphElement, *args,
                 vertex1: FigureVertex = None,
                 vertex2: FigureVertex = None, **kwargs):
        FigureElement.__init__(self, graph_element)
        if vertex1 is not None and vertex2 is not None:
            center1 = vertex1.center
            center2 = vertex2.center
            plt.Line2D.__init__(self, (center1[0], center2[0]),
                                (center1[1], center2[1]), *args, **kwargs)
            vertex1.edges.add(self)
            vertex2.edges.add(self)
        else:
            plt.Line2D.__init__(self, *args, **kwargs)
        self.vertex1: FigureVertex = vertex1
        """The first Vertex connected to this Edge."""
        self.vertex2: FigureVertex = vertex2
        """The second Vertex connected to this Edge."""

    def update_position(self):
        """
        Update the position of the Edge based on the connected Edges.
        """
        center1 = self.vertex1.center
        center2 = self.vertex2.center
        self.set_xdata((center1[0], center2[0]))
        self.set_ydata((center1[1], center2[1]))

    def get_center(self) -> Tuple[int, int]:
        x1, x2 = self.get_xdata()
        y1, y2 = self.get_ydata()
        center = (x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
        return center

    def update_path_effects(self) -> None:
        """
        Updates the applied path effects.
        """
        effects = list(self.extra_path_effects.values())
        effects.append(pe.Normal())
        self.set_path_effects(effects)

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        super().add_extra_path_effect(name, effect)
        self.update_path_effects()

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        super().remove_extra_path_effect(name)
        self.update_path_effects()

    def on_position_change(self):
        self.update_position()
        if self.annotation is not None:
            self.annotation.xy = self.get_center()

    def on_hover(self):
        log.debug(f'Setting path effect on {self}')
        self.add_extra_path_effect('hover',
                                   pe.Stroke(linewidth=3, foreground='r'))

    def on_unhover(self):
        log.debug(f'Unsetting path effect on {self}')
        self.remove_extra_path_effect('hover')
