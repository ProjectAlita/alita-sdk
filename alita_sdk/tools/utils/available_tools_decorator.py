def extend_with_parent_available_tools(method):
    def wrapper(self, *args, **kwargs):
        child_tools = method(self, *args, **kwargs)
        parent_tools = super(self.__class__, self).get_available_tools()
        return parent_tools + child_tools
    return wrapper