# sandbox.py

**Path:** `src/alita_sdk/utils/sandbox.py`

## Data Flow

The data flow within `sandbox.py` is primarily concerned with setting up a secure environment for executing arbitrary code. The data originates from the `sys.argv` array, which captures command-line arguments passed to the script. Specifically, the code to be executed is expected to be the first argument (`sys.argv[1]`). This code is then processed through a series of functions designed to impose strict resource limits and permissions.

The `exec_code` function is the entry point for this data. It retrieves the code from `sys.argv[1]`, sets memory and CPU time limits using `set_mem_limit`, and drops unnecessary permissions using `drop_perms`. Finally, it executes the code using Python's built-in `exec` function.

Here is a key snippet illustrating this data flow:

```python
code = sys.argv[1]  # Retrieve code from command-line arguments
set_mem_limit()  # Set resource limits
 drop_perms()  # Drop unnecessary permissions
return exec(code)  # Execute the code
```

In this example, the data (code to be executed) flows from the command-line arguments, through the resource-limiting and permission-dropping functions, and finally to the `exec` function for execution.

## Functions Descriptions

### `drop_perms`

The `drop_perms` function is responsible for setting up a seccomp filter that restricts the system calls the executed code can make. It primarily allows writing to `stdout` and `stderr` while blocking other operations by responding with `EPERM` (operation not permitted).

- **Inputs:** None
- **Processing:**
  - Creates a seccomp filter with a default action of returning `EPERM`.
  - Adds rules to allow writing to `stdout` and `stderr`.
  - Loads the filter into the kernel.
- **Outputs:** None

### `set_mem_limit`

The `set_mem_limit` function sets resource limits for the executed code, including virtual memory, CPU time, and file size for `stdout`/`stderr`.

- **Inputs:** None
- **Processing:**
  - Sets virtual memory limit to 64MB.
  - Sets CPU time limit to 1 second.
  - Sets file size limit for `stdout`/`stderr` to 512 bytes.
- **Outputs:** None

### `exec_code`

The `exec_code` function is the main entry point for executing arbitrary code with imposed limits.

- **Inputs:**
  - `code` (str): The code to be executed, retrieved from `sys.argv[1]`.
- **Processing:**
  - Calls `set_mem_limit` to impose resource limits.
  - Calls `drop_perms` to restrict system calls.
  - Executes the code using `exec`.
- **Outputs:** None

## Dependencies Used and Their Descriptions

### `sys`

- **Purpose:** Used to retrieve command-line arguments and interact with the Python runtime environment.
- **Usage:** `sys.argv[1]` to get the code to be executed.

### `resource`

- **Purpose:** Used to set resource limits for the executed code.
- **Usage:** `resource.setrlimit` to set limits on virtual memory, CPU time, and file size.

### `pyseccomp`

- **Purpose:** Used to create and manage seccomp filters for restricting system calls.
- **Usage:**
  - `seccomp.SyscallFilter` to create a new filter.
  - `filter.add_rule` to add rules to the filter.
  - `filter.load` to load the filter into the kernel.

## Functional Flow

The functional flow of `sandbox.py` is straightforward and linear. The script starts by defining constants for resource limits. It then defines three functions: `drop_perms`, `set_mem_limit`, and `exec_code`.

1. **Initialization:** Constants for memory, CPU time, and write limits are defined.
2. **Function Definitions:**
   - `drop_perms`: Sets up seccomp filter.
   - `set_mem_limit`: Sets resource limits.
   - `exec_code`: Main function to execute code with limits.
3. **Execution:** The `exec_code` function is called, which retrieves the code from `sys.argv[1]`, sets limits, drops permissions, and executes the code.

Here is a high-level overview of the functional flow:

```python
code = sys.argv[1]  # Step 1: Retrieve code
set_mem_limit()  # Step 2: Set resource limits
drop_perms()  # Step 3: Drop permissions
return exec(code)  # Step 4: Execute code
```

## Endpoints Used/Created

The `sandbox.py` script does not explicitly define or call any network endpoints. Its primary focus is on setting up a secure environment for executing arbitrary code by imposing resource limits and restricting system calls.