# sandbox.py

**Path:** `src/alita_sdk/utils/sandbox.py`

## Data Flow

The data flow within `sandbox.py` is centered around the execution of user-provided code within a restricted environment. The primary data elements include the user-provided code, memory limits, CPU time limits, and write limits. The data flow can be summarized as follows:

1. **Input:** The user-provided code is passed as a command-line argument (`sys.argv[1]`).
2. **Transformation:** The code undergoes several transformations to ensure it runs within the specified resource limits. This includes setting memory limits, CPU time limits, and write limits using the `resource` module.
3. **Execution:** The transformed code is executed within the restricted environment using the `exec` function.
4. **Output:** The result of the code execution is returned.

Example:
```python
code = sys.argv[1]
set_mem_limit()
drop_perms()
return exec(code)
```
In this example, the user-provided code is first assigned to the `code` variable. The `set_mem_limit` and `drop_perms` functions are called to set resource limits and drop permissions, respectively. Finally, the code is executed using the `exec` function.

## Functions Descriptions

### drop_perms

The `drop_perms` function is responsible for setting up a seccomp filter to restrict the system calls that the executed code can make. It allows writing to `stdout` and `stderr` but blocks other operations by responding with `EPERM` (operation not permitted).

**Inputs:** None

**Processing Logic:**
- Creates a seccomp filter with `EPERM` as the default action.
- Adds rules to allow writing to `stdout` and `stderr`.
- Loads the filter into the kernel.

**Outputs:** None

Example:
```python
filter = seccomp.SyscallFilter(seccomp.ERRNO(seccomp.errno.EPERM))
filter.add_rule(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, sys.stdout.fileno()))
filter.add_rule(seccomp.ALLOW, "write", seccomp.Arg(0, seccomp.EQ, sys.stderr.fileno()))
filter.load()
```
In this example, a seccomp filter is created with `EPERM` as the default action. Rules are added to allow writing to `stdout` and `stderr`, and the filter is loaded into the kernel.

### set_mem_limit

The `set_mem_limit` function sets resource limits for the executed code using the `resource` module. It sets limits for virtual memory, CPU time, and file size.

**Inputs:** None

**Processing Logic:**
- Sets the virtual memory limit to `MEMORY_LIMIT`.
- Sets the CPU time limit to `CPU_TIME_LIMIT`.
- Sets the file size limit to `WRITE_LIMIT`.

**Outputs:** None

Example:
```python
resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_LIMIT, CPU_TIME_LIMIT))
resource.setrlimit(resource.RLIMIT_FSIZE, (WRITE_LIMIT, WRITE_LIMIT))
```
In this example, the virtual memory limit, CPU time limit, and file size limit are set using the `resource` module.

### exec_code

The `exec_code` function is responsible for executing the user-provided code within the restricted environment. It sets resource limits and drops permissions before executing the code.

**Inputs:**
- `code`: The user-provided code to be executed.

**Processing Logic:**
- Sets resource limits by calling `set_mem_limit`.
- Drops permissions by calling `drop_perms`.
- Executes the code using the `exec` function.

**Outputs:** The result of the executed code.

Example:
```python
code = sys.argv[1]
set_mem_limit()
drop_perms()
return exec(code)
```
In this example, the user-provided code is first assigned to the `code` variable. The `set_mem_limit` and `drop_perms` functions are called to set resource limits and drop permissions, respectively. Finally, the code is executed using the `exec` function.

## Dependencies Used and Their Descriptions

### sys

The `sys` module provides access to system-specific parameters and functions. In `sandbox.py`, it is used to retrieve command-line arguments (`sys.argv`) and file descriptors for `stdout` and `stderr`.

### resource

The `resource` module provides an interface for setting and getting resource limits. In `sandbox.py`, it is used to set limits for virtual memory, CPU time, and file size.

### pyseccomp (seccomp)

The `pyseccomp` module provides an interface for setting up seccomp filters to restrict system calls. In `sandbox.py`, it is used to create a seccomp filter that restricts the system calls that the executed code can make.

## Functional Flow

The functional flow of `sandbox.py` involves the following steps:

1. **Retrieve User-Provided Code:** The user-provided code is retrieved from the command-line arguments (`sys.argv[1]`).
2. **Set Resource Limits:** The `set_mem_limit` function is called to set limits for virtual memory, CPU time, and file size.
3. **Drop Permissions:** The `drop_perms` function is called to set up a seccomp filter that restricts system calls.
4. **Execute Code:** The user-provided code is executed using the `exec` function.

Example:
```python
code = sys.argv[1]
set_mem_limit()
drop_perms()
return exec(code)
```
In this example, the user-provided code is first assigned to the `code` variable. The `set_mem_limit` and `drop_perms` functions are called to set resource limits and drop permissions, respectively. Finally, the code is executed using the `exec` function.

## Endpoints Used/Created

There are no explicit endpoints used or created in `sandbox.py`. The functionality is focused on executing user-provided code within a restricted environment without interacting with external endpoints.
