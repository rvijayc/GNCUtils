# GNUCash Debug Logging Guide

## 🔍 Overview
GNUCash uses a comprehensive logging system based on GLib that can help debug issues with Python bindings, session management, and transaction processing.

## 🛠️ Proper Python Bindings Method (RECOMMENDED)

The correct way to enable GNUCash logging from Python bindings is through the logging configuration file system using `qof_log_init()` and `qof_log_parse_log_config()`:

### **Using Log Configuration Files**

```python
from gnucash import gnucash_core_c

# Initialize and configure logging
gnucash_core_c.qof_log_init()
gnucash_core_c.qof_log_parse_log_config("log.conf")
```

### **Using the Shared Module (RECOMMENDED)**

```python
from gnc_common import GnuCashSession, setup_logging

# Set up logging automatically
log_conf = setup_logging()

# Use in your script with logging enabled
with GnuCashSession(book_path, log_conf=log_conf) as book:
    # Your GNUCash operations here with logging
    pass
```

### **Log Configuration File Format (log.conf)**

GNUCash uses a structured configuration format with sections. Based on your existing log.conf:

```ini
# GNUCash Logging Configuration
# Log Levels: error, warn, info, debug

[levels]
# Core GNUCash domains
gnc=debug
gnc.bin=debug
gnc.backend=debug

# Session and backend logging (most useful for Python bindings)
gnc.session=info
gnc.backend.dbi=warn
gnc.backend.sql=warn

# Engine components
gnc.engine=debug
gnc.account=debug
gnc.transaction=debug
gnc.split=debug

# Application utilities
gnc.app-util=info

# GUI components (usually not needed for Python scripts)
gnc.gui=warn

# Python binding specific logging
python=info
swig=warn

# GLib logging (keep at error to reduce noise)
GLib=error

[output]
to=stderr
```

## 🚀 Usage Examples

### **Using Scripts with --debug Flag (EASIEST)**

```bash
# List accounts with debug logging
./gpython3 list_accounts.py ~/gnc/vijayr.gnucash --credit-cards-only --debug

# Analyze transactions with debug logging  
./gpython3 analyze_transactions.py ~/gnc/vijayr.gnucash --debug
```

### **Custom Log Configuration Files**

Create custom log configurations for different scenarios:

**Session Issues (session_debug.conf):**
```ini
[levels]
gnc.session=debug
gnc.backend=info
python=info
GLib=error

[output]
to=stderr
```

**Transaction Processing (transaction_debug.conf):**
```ini
[levels]
gnc.engine=debug
gnc.transaction=debug
gnc.split=debug
python=info
GLib=error

[output]
to=stderr
```

**Python Binding Issues (python_debug.conf):**
```ini
[levels]
python=debug
swig=debug
gnc.session=info
GLib=error

[output]
to=stderr
```

Then use them:
```python
with GnuCashSession(book_path, log_conf="session_debug.conf") as book:
    # High-detail logging for session issues
    pass
```

### **Programmatic Logging Control**

```python
from gnc_common import GnuCashSession, setup_logging

# Automatic setup with default log.conf
log_conf = setup_logging()
with GnuCashSession(book_path, log_conf=log_conf) as book:
    # Operations with logging enabled
    pass
```

## 📊 Log Levels Explained

| Level | Description |
|-------|-------------|
| error | Only error messages |
| warn  | Warnings and errors |
| info  | Informational messages, warnings, and errors |
| debug | All messages including detailed debug info |

## 🔧 Common Log Domains

- `gnc` - General GNUCash operations
- `gnc.session` - Session management
- `gnc.backend` - Database/file backend operations  
- `gnc.engine` - Core engine operations
- `gnc.account` - Account operations
- `gnc.transaction` - Transaction operations
- `gnc.split` - Split operations
- `python` - Python binding specific logs
- `swig` - SWIG binding layer
- `GLib` - GLib library messages

## 🚫 Environment Variables (DEPRECATED FOR PYTHON BINDINGS)

**Note**: Environment variables like `GNC_LOG_LEVEL` and `GNC_LOG_DOMAIN` may not work consistently with Python bindings. Use the configuration file method above instead.

## 🚨 Log Output Management

### **Redirect to File**
```bash
./gpython3 your_script.py 2> debug.log
# or
./gpython3 your_script.py > output.log 2>&1
```

### **Filter Specific Messages**
```bash
# Show only ERROR and WARN messages
./gpython3 your_script.py 2>&1 | grep -E "(ERROR|WARN)"

# Show only session-related messages
./gpython3 your_script.py 2>&1 | grep -i session
```

## ⚠️ Performance Impact

**Warning**: Debug-level logging can significantly impact performance and generate large amounts of output. Use it only when debugging specific issues.

**Recommendations**:
- Start with `info` level for general debugging
- Use `debug` only for specific problem diagnosis
- Always specify relevant domains rather than using blanket debug settings

## 🔍 Troubleshooting Common Issues

### **Session Connection Issues**
```ini
[levels]
gnc.session=debug
gnc.backend=debug
```

### **SQLite3 Database Issues**
```ini
[levels]
gnc.backend=debug
gnc.backend.dbi=debug
gnc.backend.sql=debug
```

### **Python Binding Issues**
```ini
[levels]
python=debug
swig=debug
```

### **Account/Transaction Access Issues**
```ini
[levels]
gnc.engine=debug
gnc.account=debug
gnc.transaction=debug
```

## 📚 Additional Resources

- **GNUCash Wiki**: https://wiki.gnucash.org/wiki/Debugging
- **GNUCash Logging Wiki**: https://wiki.gnucash.org/wiki/Logging  
- **Doxygen Documentation**: https://code.gnucash.org/docs/STABLE/group__Logging.html
- **Mailing List Discussion**: https://lists.gnucash.org/pipermail/gnucash-devel/2007-February/019836.html

**Pro Tip**: Use the shared `gnc_common` module with `GnuCashSession` for automatic logging setup!
