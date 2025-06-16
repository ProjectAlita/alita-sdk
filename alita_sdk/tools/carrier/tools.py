# import all available tools
from .tickets_tool import FetchTicketsTool, CreateTicketTool
from .backend_reports_tool import GetReportsTool, GetReportByIDTool, CreateExcelReportTool
from .backend_tests_tool import GetTestsTool, GetTestByIDTool, RunTestByIDTool


__all__ = [
    {"name": "get_ticket_list", "tool": FetchTicketsTool},
    {"name": "create_ticket", "tool": CreateTicketTool},
    {"name": "get_reports", "tool": GetReportsTool},
    {"name": "get_report_by_id", "tool": GetReportByIDTool},
    {"name": "create_excel_report", "tool": CreateExcelReportTool},
    {"name": "get_tests", "tool": GetTestsTool},
    {"name": "get_test_by_id", "tool": GetTestByIDTool},
    {"name": "run_test_by_id", "tool": RunTestByIDTool}
]
