# Markdown with Code Blocks

This file tests the loader's ability to handle fenced code blocks in markdown.

## Python Code Example

Here's a simple Python function:

```python
def calculate_fibonacci(n):
    """
    Calculate Fibonacci sequence up to n terms.
    Returns a list of Fibonacci numbers.
    """
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    
    return fib

# Example usage
result = calculate_fibonacci(10)
print(f"Fibonacci sequence: {result}")
```

## JavaScript Code Example

And here's a JavaScript implementation:

```javascript
function calculateFibonacci(n) {
    /**
     * Calculate Fibonacci sequence up to n terms
     * @param {number} n - Number of terms to generate
     * @returns {Array} - Array of Fibonacci numbers
     */
    if (n <= 0) return [];
    if (n === 1) return [0];
    if (n === 2) return [0, 1];
    
    const fib = [0, 1];
    for (let i = 2; i < n; i++) {
        fib.push(fib[i-1] + fib[i-2]);
    }
    
    return fib;
}

// Example usage
const result = calculateFibonacci(10);
console.log(`Fibonacci sequence: ${result}`);
```

## SQL Query Example

Database query with syntax highlighting:

```sql
-- Select user data with join
SELECT 
    u.user_id,
    u.username,
    u.email,
    p.profile_name,
    p.bio,
    COUNT(o.order_id) as total_orders
FROM users u
LEFT JOIN profiles p ON u.user_id = p.user_id
LEFT JOIN orders o ON u.user_id = o.user_id
WHERE u.status = 'active'
    AND u.created_date >= '2024-01-01'
GROUP BY u.user_id, u.username, u.email, p.profile_name, p.bio
HAVING COUNT(o.order_id) > 0
ORDER BY total_orders DESC
LIMIT 100;
```

## Shell Script Example

Bash script for automation:

```bash
#!/bin/bash

# Deploy application script
set -e

APP_NAME="my-application"
VERSION="1.0.0"
DEPLOY_DIR="/opt/applications/${APP_NAME}"

echo "Starting deployment of ${APP_NAME} v${VERSION}"

# Create backup
if [ -d "${DEPLOY_DIR}" ]; then
    echo "Creating backup..."
    tar -czf "${DEPLOY_DIR}_backup_$(date +%Y%m%d_%H%M%S).tar.gz" "${DEPLOY_DIR}"
fi

# Deploy new version
echo "Deploying new version..."
mkdir -p "${DEPLOY_DIR}"
cp -r ./build/* "${DEPLOY_DIR}/"

# Restart service
echo "Restarting service..."
systemctl restart "${APP_NAME}"

echo "Deployment completed successfully! 🚀"
```

## Inline Code

You can also use `inline code` like this: `print("Hello, World!")` or `npm install package-name`.

## Mixed Content with Code

When working with APIs, you might use code like this:

```python
import requests

def fetch_user_data(user_id):
    url = f"https://api.example.com/users/{user_id}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()
```

And then process the data:

```python
user = fetch_user_data(12345)
print(f"User: {user['name']}, Email: {user['email']}")
```

## Code Block with Unicode

```python
# Unicode support test
messages = {
    'greeting': 'Hello 世界 🌍',
    'emoji': '✨ 🚀 💻 📊',
    'special': 'Café résumé naïve'
}

for key, value in messages.items():
    print(f"{key}: {value}")
```

## Conclusion

This file demonstrates various code block types that the AlitaMarkdownLoader should preserve in the page_content.
