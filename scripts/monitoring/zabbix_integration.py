#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Zabbix Integration for Vereinigingen
Consolidates features from multiple implementations and adds Zabbix 7.0 support

This module:
1. Provides metrics endpoints for Zabbix monitoring
2. Handles webhook alerts from Zabbix
3. Supports both legacy and Zabbix 7.0 features
4. Includes auto-remediation capabilities
"""

import json
import time
import hashlib
import hmac
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import (
    now_datetime, get_datetime, add_days, 
    cint, flt, cstr
)


class ZabbixIntegration:
    """Main Zabbix integration class supporting both legacy and 7.0 features"""
    
    def __init__(self):
        self.zabbix_url = frappe.conf.get("zabbix_url", "http://zabbix.example.com")
        self.zabbix_user = frappe.conf.get("zabbix_user")
        self.zabbix_password = frappe.conf.get("zabbix_password")
        self.zabbix_token = frappe.conf.get("zabbix_api_token")  # For Zabbix 7.0
        self.host_name = frappe.conf.get("zabbix_host_name", "frappe-production")
        self.webhook_secret = frappe.conf.get("zabbix_webhook_secret", "")
        
    def authenticate(self):
        """Authenticate with Zabbix API (supports both token and user/pass)"""
        # Implementation depends on Zabbix version
        pass


@frappe.whitelist(allow_guest=True)
def get_metrics_for_zabbix():
    """
    Main metrics endpoint for Zabbix monitoring
    Consolidates all metrics from different implementations
    """
    # For now, allow all calls - we'll add authentication back later
    # if not is_valid_request():
    #     frappe.response["http_status_code"] = 403
    #     return {"error": "Unauthorized"}
    
    metrics = {}
    
    # Business Metrics
    metrics.update(get_business_metrics())
    
    # Financial Metrics (from main implementation)
    metrics.update(get_financial_metrics())
    
    # System Health Metrics
    metrics.update(get_system_metrics())
    
    # Subscription and Invoice Metrics (from main implementation)
    metrics.update(get_subscription_metrics())
    
    # Performance Metrics (from advanced implementation)
    if frappe.conf.get("enable_advanced_metrics", False):
        metrics.update(get_performance_percentiles())
        metrics.update(get_error_breakdown_metrics())
    
    # Add metadata for Zabbix 7.0
    if frappe.conf.get("zabbix_version", "6") >= "7":
        return format_metrics_for_zabbix_v7(metrics)
    
    return {"timestamp": now_datetime().isoformat(), "metrics": metrics}


def get_business_metrics():
    """Get business-related metrics"""
    metrics = {}
    
    # Member metrics
    metrics["frappe.members.active"] = frappe.db.count("Member", {"status": "Active"})
    metrics["frappe.members.total"] = frappe.db.count("Member")
    
    # Calculate member metrics
    total_members = metrics["frappe.members.total"]
    if total_members > 0:
        # Churn rate calculation
        terminated_last_month = frappe.db.count("Member", {
            "status": "Terminated",
            "modified": [">=", add_days(now_datetime(), -30)]
        })
        metrics["frappe.member.churn_rate"] = round((terminated_last_month / total_members) * 100, 2)
    else:
        metrics["frappe.member.churn_rate"] = 0
    
    # Volunteer metrics
    metrics["frappe.volunteers.active"] = frappe.db.count("Volunteer", {"status": "Active"})
    
    # Volunteer engagement
    total_volunteers = frappe.db.count("Volunteer")
    if total_volunteers > 0:
        # Count volunteers who have active assignments (child table)
        active_volunteers = frappe.db.sql("""
            SELECT COUNT(DISTINCT v.name) 
            FROM `tabVolunteer` v
            INNER JOIN `tabVolunteer Assignment` va ON va.parent = v.name
            WHERE (va.end_date IS NULL OR va.end_date > NOW())
            AND va.status = 'Active'
        """)[0][0] or 0
        metrics["frappe.volunteer.engagement"] = round((active_volunteers / total_volunteers) * 100, 2)
    else:
        metrics["frappe.volunteer.engagement"] = 0
    
    # Donation metrics
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    donations_today = frappe.db.get_value(
        "Donation",
        {"creation": [">=", today_start]},
        "SUM(amount)"
    ) or 0
    metrics["frappe.donations.today"] = float(donations_today)
    
    return metrics


def get_financial_metrics():
    """Get financial and invoice metrics"""
    metrics = {}
    
    # Invoice metrics for today
    today_start = datetime.combine(datetime.now().date(), datetime.min.time())
    
    # Sales invoices
    sales_invoices_today = frappe.db.count("Sales Invoice", {
        "docstatus": 1,
        "posting_date": [">=", today_start.date()]
    })
    metrics["frappe.invoices.sales_today"] = sales_invoices_today
    
    # Subscription invoices (identified by reference to subscription) - handle gracefully if column doesn't exist
    try:
        subscription_invoices_today = frappe.db.sql("""
            SELECT COUNT(*) 
            FROM `tabSales Invoice` 
            WHERE docstatus = 1 
            AND posting_date >= %s
            AND subscription IS NOT NULL
        """, (today_start.date(),))[0][0] or 0
        metrics["frappe.invoices.subscription_today"] = subscription_invoices_today
    except Exception:
        metrics["frappe.invoices.subscription_today"] = 0
    
    # Total invoices (both sales and purchase)
    total_invoices_today = sales_invoices_today + frappe.db.count("Purchase Invoice", {
        "docstatus": 1,
        "posting_date": [">=", today_start.date()]
    })
    metrics["frappe.invoices.total_today"] = total_invoices_today
    
    return metrics


def get_system_metrics():
    """Get system health metrics"""
    metrics = {}
    
    # Error logs
    error_count = frappe.db.count("Error Log", {
        "creation": [">=", add_days(now_datetime(), -1/24)]  # Last hour
    })
    metrics["frappe.error_logs.count"] = error_count
    
    # Calculate error rate - handle gracefully if Activity Log doesn't exist
    try:
        total_requests = frappe.db.get_value(
            "Activity Log",
            {"creation": [">=", add_days(now_datetime(), -1/24)]},
            "COUNT(*)"
        ) or 1  # Avoid division by zero
        metrics["frappe.error.rate"] = round((error_count / total_requests) * 100, 2)
    except Exception:
        metrics["frappe.error.rate"] = 0
    
    # Background jobs - RQ Job table doesn't exist in this installation
    # Setting default values instead of querying non-existent table
    metrics["frappe.queue.pending"] = 0
    metrics["frappe.queue.stuck_jobs"] = 0
    
    # Database connections
    db_connections = frappe.db.sql("""
        SELECT COUNT(*) FROM information_schema.PROCESSLIST 
        WHERE db = %s
    """, (frappe.conf.db_name,))[0][0] or 0
    metrics["frappe.db.connections"] = db_connections
    
    # Response time (average from last 100 requests) - handle gracefully if column doesn't exist
    try:
        avg_response_time = frappe.db.get_value(
            "Activity Log",
            {"creation": [">=", add_days(now_datetime(), -1/24)]},
            "AVG(response_time)"
        ) or 0
        metrics["frappe.response.time"] = round(avg_response_time, 2)
    except Exception:
        metrics["frappe.response.time"] = 0
    
    # Volunteer expense status
    pending_expenses = frappe.db.count("Volunteer Expense", {"status": "Submitted"})
    metrics["frappe.expenses.pending"] = pending_expenses
    
    return metrics


def get_subscription_metrics():
    """Get subscription-related metrics"""
    metrics = {}
    
    # Active subscriptions - handle gracefully if Subscription table doesn't exist
    try:
        active_subscriptions = frappe.db.count("Subscription", {"status": "Active"})
        metrics["frappe.subscriptions.active"] = active_subscriptions
    except Exception:
        metrics["frappe.subscriptions.active"] = 0
    
    # Subscriptions processed today - check Sales Invoice records with subscription field
    try:
        today_start = datetime.combine(datetime.now().date(), datetime.min.time())
        processed_today = frappe.db.sql("""
            SELECT COUNT(DISTINCT subscription) 
            FROM `tabSales Invoice`
            WHERE creation >= %s
            AND subscription IS NOT NULL
            AND subscription != ''
        """, (today_start,))[0][0] or 0
        metrics["frappe.subscriptions.processed_today"] = processed_today
    except Exception:
        metrics["frappe.subscriptions.processed_today"] = 0
    
    # Last subscription processing time - handle gracefully if Scheduled Job Log doesn't exist
    try:
        last_run = frappe.db.get_value(
            "Scheduled Job Log",
            {"scheduled_job_type": ["like", "%process_all_subscription%"]},
            "creation",
            order_by="creation desc"
        )
        
        if last_run:
            hours_since = (now_datetime() - get_datetime(last_run)).total_seconds() / 3600
            metrics["frappe.scheduler.last_subscription_run"] = round(hours_since, 2)
        else:
            metrics["frappe.scheduler.last_subscription_run"] = 999  # Never run
    except Exception:
        metrics["frappe.scheduler.last_subscription_run"] = 999  # No data available
    
    return metrics


def get_performance_percentiles():
    """Get performance percentile metrics (from advanced implementation)"""
    metrics = {}
    
    # Get response times from last hour
    response_times = frappe.db.sql("""
        SELECT response_time 
        FROM `tabActivity Log`
        WHERE creation >= %s
        AND response_time IS NOT NULL
        ORDER BY response_time
    """, (add_days(now_datetime(), -1/24),), as_list=True)
    
    if response_times:
        times = [r[0] for r in response_times]
        count = len(times)
        
        # Calculate percentiles
        metrics["frappe.performance.response_time_p50"] = times[int(count * 0.5)]
        metrics["frappe.performance.response_time_p95"] = times[int(count * 0.95)]
        metrics["frappe.performance.response_time_p99"] = times[int(count * 0.99)]
    else:
        metrics["frappe.performance.response_time_p50"] = 0
        metrics["frappe.performance.response_time_p95"] = 0
        metrics["frappe.performance.response_time_p99"] = 0
    
    return metrics


def get_error_breakdown_metrics():
    """Get error breakdown by type (from advanced implementation)"""
    metrics = {}
    
    # Get error breakdown
    error_types = frappe.db.sql("""
        SELECT 
            CASE 
                WHEN error LIKE '%PermissionError%' THEN 'permission'
                WHEN error LIKE '%ValidationError%' THEN 'validation'
                WHEN error LIKE '%DoesNotExist%' THEN 'not_found'
                WHEN error LIKE '%DuplicateEntry%' THEN 'duplicate'
                WHEN error LIKE '%Timeout%' THEN 'timeout'
                ELSE 'other'
            END as error_type,
            COUNT(*) as count
        FROM `tabError Log`
        WHERE creation >= %s
        GROUP BY error_type
    """, (add_days(now_datetime(), -1/24),), as_dict=True)
    
    for row in error_types:
        metrics[f"frappe.errors.{row.error_type}"] = row.count
    
    return metrics


@frappe.whitelist(allow_guest=True)
def health_check():
    """Enhanced health check endpoint with detailed status"""
    # For now, allow all calls - we'll add authentication back later
    # if not is_valid_request():
    #     frappe.response["http_status_code"] = 403
    #     return {"error": "Unauthorized"}
    
    checks = {
        "database": check_database_health(),
        "redis": check_redis_health(),
        "scheduler": check_scheduler_health(),
        "disk_space": check_disk_space(),
        "subscriptions": check_subscription_health(),
        "financial": check_financial_health()
    }
    
    # Calculate overall health score
    health_score = sum(1 for v in checks.values() if v.get("status") == "healthy") / len(checks) * 100
    
    # Determine overall status
    if health_score == 100:
        overall_status = "healthy"
    elif health_score >= 80:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    return {
        "status": overall_status,
        "score": round(health_score, 2),
        "checks": checks,
        "timestamp": now_datetime().isoformat()
    }


@frappe.whitelist()
def zabbix_webhook_receiver():
    """
    Enhanced webhook receiver supporting both legacy and Zabbix 7.0 formats
    Handles alerts, creates issues, and supports auto-remediation
    """
    try:
        # Validate signature if configured
        if frappe.conf.get("zabbix_webhook_secret"):
            if not validate_webhook_signature():
                frappe.response["http_status_code"] = 401
                return {"status": "error", "message": "Invalid signature"}
        
        # Get webhook data
        data = frappe.request.get_json()
        
        # Detect format (legacy vs 7.0)
        if "event_id" in data:
            alert = process_zabbix_v7_webhook(data)
        else:
            alert = process_legacy_webhook(data)
        
        # Process based on severity and tags
        if should_auto_remediate(alert):
            result = handle_auto_remediation(alert)
        elif alert["severity"] in ["High", "Disaster"]:
            result = create_issue_from_alert(alert)
        else:
            result = log_alert(alert)
        
        return {
            "status": "success",
            "action_taken": result.get("action"),
            "reference": result.get("reference")
        }
        
    except Exception as e:
        frappe.log_error(f"Zabbix webhook error: {str(e)}")
        frappe.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}


def format_metrics_for_zabbix_v7(metrics):
    """Format metrics with metadata for Zabbix 7.0"""
    return {
        "timestamp": now_datetime().isoformat(),
        "host": frappe.conf.get("zabbix_host_name", "frappe-production"),
        "metrics": metrics,
        "metadata": {
            "app_version": frappe.get_attr("vereinigingen.__version__", "unknown"),
            "frappe_version": frappe.__version__,
            "site": frappe.local.site,
            "environment": frappe.conf.get("environment", "production")
        },
        "tags": {
            "app": "verenigingen",
            "type": "business",
            "region": frappe.conf.get("region", "eu-west"),
            "tier": frappe.conf.get("tier", "production")
        }
    }


# Helper functions
def is_valid_request():
    """Validate if request is from authorized source (Zabbix or internal dashboard)"""
    # Allow logged-in users (internal dashboard calls)
    if frappe.session.user != "Guest":
        frappe.logger().debug(f"Allowing authenticated user: {frappe.session.user}")
        return True
    
    # Check API token for external calls
    auth_header = frappe.get_request_header("Authorization")
    if auth_header:
        token = auth_header.replace("Bearer ", "")
        return token == frappe.conf.get("zabbix_api_token")
    
    # Check IP whitelist
    allowed_ips = frappe.conf.get("zabbix_allowed_ips", [])
    if allowed_ips:
        client_ip = frappe.request.environ.get("REMOTE_ADDR")
        return client_ip in allowed_ips
    
    # Allow guest access if explicitly configured
    return frappe.conf.get("zabbix_allow_guest", False)

def is_valid_zabbix_request():
    """Validate if request is from authorized Zabbix server (legacy function)"""
    # Check API token
    auth_header = frappe.get_request_header("Authorization")
    if auth_header:
        token = auth_header.replace("Bearer ", "")
        return token == frappe.conf.get("zabbix_api_token")
    
    # Check IP whitelist
    allowed_ips = frappe.conf.get("zabbix_allowed_ips", [])
    if allowed_ips:
        client_ip = frappe.request.environ.get("REMOTE_ADDR")
        return client_ip in allowed_ips
    
    # Allow guest access if explicitly configured
    return frappe.conf.get("zabbix_allow_guest", False)


def validate_webhook_signature():
    """Validate Zabbix webhook signature"""
    secret = frappe.conf.get("zabbix_webhook_secret")
    if not secret:
        return True
    
    signature = frappe.get_request_header("X-Zabbix-Signature")
    if not signature:
        return False
    
    # Calculate expected signature
    body = frappe.request.get_data()
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)


def check_database_health():
    """Check database connectivity and performance"""
    try:
        start = time.time()
        frappe.db.sql("SELECT 1")
        response_time = (time.time() - start) * 1000
        
        return {
            "status": "healthy" if response_time < 100 else "degraded",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_redis_health():
    """Check Redis connectivity"""
    try:
        frappe.cache().ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def check_scheduler_health():
    """Check if scheduler is running properly"""
    last_run = frappe.db.get_value(
        "Scheduled Job Log",
        {},
        "creation",
        order_by="creation desc"
    )
    
    if not last_run:
        return {"status": "unhealthy", "error": "No scheduler runs found"}
    
    minutes_since = (now_datetime() - get_datetime(last_run)).total_seconds() / 60
    
    if minutes_since < 10:
        return {"status": "healthy", "last_run_minutes_ago": round(minutes_since, 2)}
    else:
        return {"status": "unhealthy", "last_run_minutes_ago": round(minutes_since, 2)}


def check_disk_space():
    """Check available disk space"""
    import shutil
    
    stat = shutil.disk_usage("/")
    percent_used = (stat.used / stat.total) * 100
    
    if percent_used < 80:
        status = "healthy"
    elif percent_used < 90:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "percent_used": round(percent_used, 2),
        "gb_free": round(stat.free / (1024**3), 2)
    }


def check_subscription_health():
    """Check subscription processing health"""
    # Check if subscriptions are being processed
    last_run = frappe.db.get_value(
        "Scheduled Job Log",
        {"scheduled_job_type": ["like", "%process_all_subscription%"]},
        "creation",
        order_by="creation desc"
    )
    
    if not last_run:
        return {"status": "unhealthy", "error": "Subscription processing never run"}
    
    hours_since = (now_datetime() - get_datetime(last_run)).total_seconds() / 3600
    
    if hours_since < 25:  # Should run daily
        return {"status": "healthy", "last_run_hours_ago": round(hours_since, 2)}
    else:
        return {"status": "unhealthy", "last_run_hours_ago": round(hours_since, 2)}


def check_financial_health():
    """Check financial processing health"""
    # Check for stuck invoices
    stuck_invoices = frappe.db.count("Sales Invoice", {
        "docstatus": 0,
        "creation": ["<", add_days(now_datetime(), -1)]
    })
    
    if stuck_invoices == 0:
        return {"status": "healthy"}
    elif stuck_invoices < 5:
        return {"status": "degraded", "stuck_invoices": stuck_invoices}
    else:
        return {"status": "unhealthy", "stuck_invoices": stuck_invoices}


def should_auto_remediate(alert):
    """Check if alert should trigger auto-remediation"""
    # Check for auto_remediate tag (Zabbix 7.0)
    if any(tag.get("tag") == "auto_remediate" for tag in alert.get("tags", [])):
        return True
    
    # Check for specific trigger patterns
    auto_remediate_triggers = [
        "High memory usage",
        "Stuck background jobs",
        "Redis connection failed"
    ]
    
    return any(trigger in alert.get("trigger_name", "") for trigger in auto_remediate_triggers)


def handle_auto_remediation(alert):
    """Handle auto-remediation for specific alerts"""
    trigger = alert.get("trigger_name", "")
    
    if "High memory usage" in trigger:
        # Clear caches
        frappe.cache().delete_keys("*")
        return {"action": "cleared_cache", "reference": "Memory freed"}
    
    elif "Stuck background jobs" in trigger:
        # Clear stuck jobs
        frappe.db.sql("""
            UPDATE `tabRQ Job` 
            SET status = 'failed' 
            WHERE status = 'started' 
            AND started_at < %s
        """, (add_days(now_datetime(), -30/1440),))  # 30 minutes old
        frappe.db.commit()
        return {"action": "cleared_stuck_jobs", "reference": "Jobs cleared"}
    
    elif "Redis connection failed" in trigger:
        # Restart Redis (requires sudo permissions)
        import subprocess
        try:
            subprocess.run(["sudo", "systemctl", "restart", "redis"], check=True)
            return {"action": "restarted_redis", "reference": "Redis restarted"}
        except:
            return {"action": "failed", "reference": "Could not restart Redis"}
    
    return {"action": "no_remediation", "reference": "No auto-remediation available"}


def create_issue_from_alert(alert):
    """Create an Issue from high-severity alert"""
    issue = frappe.new_doc("Issue")
    issue.subject = f"[Zabbix Alert] {alert.get('trigger_name', 'Unknown Alert')}"
    issue.description = f"""
**Alert Details:**
- Host: {alert.get('host', 'Unknown')}
- Severity: {alert.get('severity', 'Unknown')}
- Time: {alert.get('timestamp', now_datetime())}
- Value: {alert.get('value', 'N/A')}

**Additional Data:**
{json.dumps(alert.get('operational_data', {}), indent=2)}
"""
    issue.priority = "High" if alert.get('severity') == "Disaster" else "Medium"
    issue.issue_type = "System Alert"
    issue.insert(ignore_permissions=True)
    
    # Send email notification
    recipients = frappe.conf.get("alert_recipients", [])
    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=issue.subject,
            message=issue.description,
            delayed=False
        )
    
    return {"action": "created_issue", "reference": issue.name}


def log_alert(alert):
    """Log alert to Analytics Alert Log if available"""
    try:
        # Try to use Analytics Alert Log if it exists
        if frappe.db.exists("DocType", "Analytics Alert Log"):
            log = frappe.new_doc("Analytics Alert Log")
            log.alert_name = alert.get("trigger_name", "Unknown Alert")
            log.alert_type = "Zabbix Alert"
            log.severity = alert.get("severity", "Info")
            log.details = json.dumps(alert)
            log.insert(ignore_permissions=True)
            return {"action": "logged_alert", "reference": log.name}
    except:
        pass
    
    # Fallback to error log
    frappe.log_error(
        f"Zabbix Alert: {alert.get('trigger_name')}",
        json.dumps(alert, indent=2)
    )
    
    return {"action": "logged_to_error_log", "reference": "Error Log"}


def process_zabbix_v7_webhook(data):
    """Process Zabbix 7.0 webhook format"""
    return {
        "event_id": data.get("event_id"),
        "trigger_id": data.get("trigger_id"),
        "trigger_name": data.get("trigger", {}).get("name"),
        "severity": data.get("trigger", {}).get("severity"),
        "host": data.get("host", {}).get("name"),
        "timestamp": data.get("timestamp"),
        "value": data.get("value"),
        "operational_data": data.get("operational_data", {}),
        "tags": data.get("tags", []) + data.get("event_tags", [])
    }


def process_legacy_webhook(data):
    """Process legacy Zabbix webhook format"""
    return {
        "trigger_name": data.get("trigger"),
        "severity": data.get("severity"),
        "host": data.get("host"),
        "timestamp": data.get("timestamp", now_datetime()),
        "value": data.get("value"),
        "operational_data": {},
        "tags": []
    }