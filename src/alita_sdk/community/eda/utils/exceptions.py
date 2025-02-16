""" This module contains exceptions for the project """
# pylint: disable=too-few-public-methods


class ResponseCodeHandler:
    """This lass handles response codes from the API."""
    def __init__(self, project_id):
        self.project_id = project_id

    def process_response_code(self, code):
        """Process response code from the API."""
        if code == 401:
            raise UnauthorizedAccess(self.project_id)
        if code == 403:
            raise AbsentAccessToRepository(self.project_id)
        if code == 404:
            raise NotFoundException(self.project_id)
        if code == 204:
            raise Unknown(self.project_id)


class NotFoundException(Exception):
    """Exception for the case when the project is not found."""
    def __init__(self, project_id):
        super().__init__(f"You have no access to the project {project_id}")


class AbsentAccessToRepository(Exception):
    """Exception for the case when the user has no access to the repository."""
    def __init__(self, project_id):
        super().__init__(f"There is no info on merge requests in the project {project_id}")


class UnauthorizedAccess(Exception):
    """Exception for the case when the user has no access to the project."""
    def __init__(self, project_id):
        super().__init__(f"Check yours authentication credentials for {project_id}")


class Unknown(Exception):
    """Exception for the case when the response code is unknown."""
    def __init__(self, project_id):
        super().__init__(f"Unknown for {project_id}")
