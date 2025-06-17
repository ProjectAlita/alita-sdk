
import re

def get_diff_w_position(change):
    diff = change["diff"]
    diff_with_ln = {}
    # Regular expression to extract old and new line numbers
    pattern = r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@"
    # GitLab API requires new path and line for added lines, old path and files for removed lines.
    # For unchaged lines it requires both. 
    for index, line in enumerate(diff.split("\n")):
        position = {}
        match = re.match(pattern, line)
        if match:
            old_line = int(match.group(1))
            new_line = int(match.group(3))
        elif line.startswith("+"):
            position["new_line"] = new_line
            position["new_path"] = change["new_path"]
            new_line += 1
        elif line.startswith("-"):
            position["old_line"] = old_line
            position["old_path"] = change["old_path"]
            old_line += 1
        elif line.startswith(" "):
            position["old_line"] = old_line
            position["old_path"] = change["old_path"]
            position["new_line"] = new_line
            position["new_path"] = change["new_path"]
            new_line += 1
            old_line += 1
        elif line.startswith("\\"):
            # Assign previos position to \\ metadata
            position = diff_with_ln[index - 1][0]
        else:
            # Stop at final empty line
            break

        diff_with_ln[index] = [position, line]

        # Assign next position to @@ metadata
        if index > 0 and diff_with_ln[index - 1][1].startswith("@"):
            diff_with_ln[index - 1][0] = position

    return diff_with_ln



def get_position(line_number, file_path, mr):
    changes = mr.changes()["changes"]
    # Get first change 
    change = next((item for item in changes if item.get("new_path") == file_path), None)
    if change == None:
        change = next((item for item in changes if item.get("old_path") == file_path), None)
    if change == None:
        raise Exception(f"Change for file {file_path} wasn't found in PR")

    position = get_diff_w_position(change=change)[line_number][0]

    position.update({
        "base_sha": mr.diff_refs["base_sha"],
        "head_sha": mr.diff_refs["head_sha"],
        "start_sha": mr.diff_refs["start_sha"],
        'position_type': 'text'
    })

    return position
