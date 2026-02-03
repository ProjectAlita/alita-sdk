# zephyr_squad - validate_toolkit

**Toolkit**: `zephyr_squad`
**Method**: `validate_toolkit`
**Source File**: `api_wrapper.py`
**Class**: `ZephyrSquadApiWrapper`

---

## Method Implementation

```python
    def validate_toolkit(cls, values):
        account_id = values.get("account_id", None)
        access_key = values.get("access_key", None)
        secret_key = values.get("secret_key", None)
        if not account_id:
            raise ValueError("account_id is required.")
        if not access_key:
            raise ValueError("access_key is required.")
        if not secret_key:
            raise ValueError("secret_key is required.")
        cls._client = ZephyrSquadCloud(
            account_id=account_id,
            access_key=access_key,
            secret_key=secret_key
        )
        return values
```
