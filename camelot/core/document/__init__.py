"""Decorators to enhance the docstrings of classes
"""

def documented_entity():
    """Class decorator to append an image of the default view for
  an entity to an entity class.  The image can be generated by using
  the testing framework to create images of all default views in an
  application ::

    @documented_entity()
    class Movie(Entity):
      '''A movie as played in the theater'''
      title = Field(Unicode(50))

  The resulting docstring of the Movie entity will be ::

    '''A movie as played in the theater

    image ../_static/entityviews/new_view_movie.png
    '''
  """

    def document_entity(model):
        model.__doc__ = (model.__doc__ or '') + """

.. image:: ../_static/entityviews/new_view_%s.png

        """%(model.__name__.lower())
        return model

    return document_entity


def documented_type():
    """Class decorator to append an image of the default editor of
  a field type to the docstring of the type"""

    def document_type(field_type):
        field_type.__doc__ = (field_type.__doc__ or '') + """

.. image:: ../_static/editors/%s_editable.png
    
    """
        return field_type

    return document_type
