# retryq

Simple task retry queue with exponential backoff built on Redis.

---

## Installation

```bash
pip install retryq
```

> Requires a running Redis instance. Install Redis locally or use a hosted provider.

---

## Usage

```python
from retryq import RetryQueue

queue = RetryQueue(redis_url="redis://localhost:6379")

# Define a task handler
@queue.task(max_retries=5, backoff_base=2)
def send_email(to, subject, body):
    # Your logic here
    pass

# Enqueue a task
send_email.enqueue(to="user@example.com", subject="Hello", body="World")

# Start processing
queue.run()
```

Retries are scheduled with exponential backoff:

| Attempt | Delay     |
|---------|-----------|
| 1       | 2 seconds |
| 2       | 4 seconds |
| 3       | 8 seconds |
| 4       | 16 seconds|
| 5       | 32 seconds|

Failed tasks that exceed `max_retries` are moved to a dead-letter queue for inspection.

---

## Configuration

| Option        | Default                    | Description                  |
|---------------|----------------------------|------------------------------|
| `redis_url`   | `redis://localhost:6379`   | Redis connection URL         |
| `max_retries` | `3`                        | Maximum retry attempts       |
| `backoff_base`| `2`                        | Base for exponential backoff |

---

## License

MIT © retryq contributors