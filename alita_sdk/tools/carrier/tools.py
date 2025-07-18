# import all available tools
from .tickets_tool import FetchTicketsTool, CreateTicketTool
from .backend_reports_tool import GetReportsTool, GetReportByIDTool, CreateExcelReportTool, AddTagToReportTool
from .backend_tests_tool import GetTestsTool, GetTestByIDTool, RunTestByIDTool, CreateBackendTestTool
from .ui_reports_tool import GetUIReportsTool, GetUIReportByIDTool, GetUITestsTool
from .run_ui_test_tool import RunUITestTool
from .update_ui_test_schedule_tool import UpdateUITestScheduleTool
from .create_ui_excel_report_tool import CreateUIExcelReportTool
from .create_ui_test_tool import CreateUITestTool
from .cancel_ui_test_tool import CancelUITestTool

__all__ = [
    {"name": "get_ticket_list", "tool": FetchTicketsTool},
    {"name": "create_ticket", "tool": CreateTicketTool},
    {"name": "get_reports", "tool": GetReportsTool},
    {"name": "get_report_by_id", "tool": GetReportByIDTool},
    {"name": "add_tag_to_report", "tool": AddTagToReportTool},
    {"name": "create_excel_report", "tool": CreateExcelReportTool},
    {"name": "get_tests", "tool": GetTestsTool},
    {"name": "get_test_by_id", "tool": GetTestByIDTool},
    {"name": "run_test_by_id", "tool": RunTestByIDTool},
    {"name": "create_backend_test", "tool": CreateBackendTestTool},
    {"name": "get_ui_reports", "tool": GetUIReportsTool},
    {"name": "get_ui_report_by_id", "tool": GetUIReportByIDTool},
    {"name": "get_ui_tests", "tool": GetUITestsTool},
    {"name": "run_ui_test", "tool": RunUITestTool},
    {"name": "update_ui_test_schedule", "tool": UpdateUITestScheduleTool},
    {"name": "create_ui_excel_report", "tool": CreateUIExcelReportTool},
    {"name": "create_ui_test", "tool": CreateUITestTool},
    {"name": "cancel_ui_test", "tool": CancelUITestTool}
]
