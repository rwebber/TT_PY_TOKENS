
import inspect
from datetime import datetime

"""
    from core.debug import debug, DebugManager
    
    # Enable debug output for specific categories
    DebugManager.enable(['collision', 'render'])
    
    # Or enable all debug output
    DebugManager.enable()
    
    # Use in your code
    debug("Processing collision", "collision")
    debug("Rendering frame", "render")
    debug("General message")  # No category
    
    # Disable specific category
    DebugManager.disable('collision')
    
    # Disable all debug output
    DebugManager.disable()
"""



class DebugManager:
    """
    Provides functionality to manage debug output with
    optional categories and caller information.

    This class allows enabling or disabling debug messages
    globally or for specific categories. It supports printing
    formatted debug messages with timestamps and caller
    information.

    :ivar _enabled: Indicates whether debug output is globally enabled.
    :type _enabled: bool
    :ivar _categories: A set of active debug categories.
    :type _categories: set
    """

    _enabled = False
    _categories = set()  # Store enabled debug categories

    @classmethod
    def enable(cls, categories=None):
        """
        Enables the functionality for specified categories or for all categories if none are provided.

        This method enables the current class and optionally restricts its operation to a set of specified
        categories. If a single category is provided as a string, it will be converted into a list. The
        categories are then stored in the class attribute `_categories`, updating its previous state.

        :param categories: Specific categories to enable the class operation for. If not provided, all
            categories will be enabled. Defaults to None.
        :type categories: list[str] or str or None
        :return: None
        :rtype: None
        """
        cls._enabled = True
        if categories:
            if isinstance(categories, str):
                categories = [categories]
            cls._categories.update(categories)

    @classmethod
    def disable(cls, categories=None):
        """
        Disable specific categories or disable the entire functionality.

        This method modifies the state of enabled categories or the overall enabled
        flag. When categories are specified, they will be removed from the existing
        set of enabled categories. If no categories are specified, the overall
        functionality will be completely disabled by clearing all categories and
        updating the enabled flag.

        :param categories: The category or list of categories to disable. If no
            categories are provided, the overall functionality will be disabled.
        :type categories: Optional[Union[str, List[str]]]
        :return: None
        :rtype: None
        """
        if categories:
            if isinstance(categories, str):
                categories = [categories]
            cls._categories.difference_update(categories)
        else:
            cls._enabled = False
            cls._categories.clear()

    @classmethod
    def is_enabled(cls, category=None):
        """
        Checks if the class-level feature is enabled and validates if the given category
        is within the allowed categories.

        This method evaluates the `_enabled` attribute and determines if the category
        is allowed based on the `_categories` attribute. If `_categories` is empty,
        all categories are considered allowed. Otherwise, it checks if `category`
        is included in the `_categories` list.

        :param category: The category to validate against the allowed categories.
        :type category: str | None
        :return: True if the feature is enabled and the category is allowed,
            False otherwise.
        :rtype: bool

        """
        return cls._enabled and (not cls._categories or category in cls._categories)

    @classmethod
    def debug(cls, *args, category=None, sep=' ', end='\n'):
        """
        Logs a debug message to the standard output. The method includes details such as
        a timestamp, optional category, caller's filename, line number, and the provided
        message content. The message will only be logged if debugging is enabled for the
        specified category.

        :param args: The positional arguments representing the content of the debug message.
                     All arguments will be converted to strings before being joined and output.
        :type args: Any
        :param category: Optional category to classify the debug message, for instance,
                         the component or module name. If None, no category is used.
        :type category: Optional[str]
        :param sep: String delimiter used to join the arguments. Defaults to a single space ' '.
        :type sep: str
        :param end: String appended to the output. Defaults to a newline character '\n'.
        :type end: str
        :return: None
        :rtype: None
        """
        if not cls.is_enabled(category):
            return

        # Get caller information
        caller_frame = inspect.currentframe().f_back
        caller_info = inspect.getframeinfo(caller_frame)

        # Format timestamp (HH:MM:SS.mmm)
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]

        # Format the debug message
        category_str = f"[{category}]" if category else ""

        # Get just the line number, no file path
        line_num = caller_info.lineno

        # Convert all arguments to strings and join them
        message = sep.join(str(arg) for arg in args)

        # Print in format: "HH:MM:SS.mmm [category] line_number - message"
        print(f"{timestamp} {category_str} {line_num} - {message}", end=end)


# Create a convenience function
def debug(*args, category=None, sep=' ', end='\n'):
    """
    Logs a debugging message using the DebugManager with specified message components,
    category, and formatting options.

    :param args: Variable length argument list containing the message components to be
        logged.
    :param category: The category under which the debug message will be logged. Defaults
        to None.
    :param sep: The string inserted between each message component in *args when
        concatenating. Defaults to a single space.
    :param end: The string appended to the end of the fully constructed debug message.
        Defaults to a newline character.
    :return: None
    :rtype: None
    """
    DebugManager.debug(*args, category=category, sep=sep, end=end)