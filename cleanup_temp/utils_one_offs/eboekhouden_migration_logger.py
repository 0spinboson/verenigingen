"""
E-Boekhouden Migration Logger

Improved logging system for E-Boekhouden migration that aggregates errors
and provides better summary information.
"""

import frappe
from collections import defaultdict
from datetime import datetime


class MigrationLogger:
    """
    A logger that aggregates similar errors and provides summary statistics
    """
    
    def __init__(self, migration_name):
        self.migration_name = migration_name
        self.start_time = datetime.now()
        
        # Statistics
        self.stats = {
            "accounts_created": 0,
            "accounts_updated": 0,
            "accounts_failed": 0,
            "transactions_created": 0,
            "transactions_failed": 0,
            "customers_created": 0,
            "customers_failed": 0,
            "suppliers_created": 0,
            "suppliers_failed": 0,
            "journal_entries_created": 0,
            "journal_entries_failed": 0,
            "payment_entries_created": 0,
            "payment_entries_failed": 0
        }
        
        # Error aggregation
        self.errors = defaultdict(list)
        self.error_counts = defaultdict(int)
        
        # Info messages (not errors)
        self.info_messages = []
        
        # Detailed error samples (keep first 5 of each type)
        self.error_samples = defaultdict(list)
        
    def log_info(self, message):
        """Log an informational message"""
        self.info_messages.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message
        })
        
    def log_success(self, operation_type, details=None):
        """Log a successful operation"""
        if operation_type == "account_created":
            self.stats["accounts_created"] += 1
        elif operation_type == "account_updated":
            self.stats["accounts_updated"] += 1
        elif operation_type == "transaction_created":
            self.stats["transactions_created"] += 1
        elif operation_type == "customer_created":
            self.stats["customers_created"] += 1
        elif operation_type == "supplier_created":
            self.stats["suppliers_created"] += 1
        elif operation_type == "journal_entry_created":
            self.stats["journal_entries_created"] += 1
        elif operation_type == "payment_entry_created":
            self.stats["payment_entries_created"] += 1
            
    def log_error(self, operation_type, error_message, details=None):
        """Log an error, aggregating similar errors"""
        # Update statistics
        if operation_type == "account_failed":
            self.stats["accounts_failed"] += 1
        elif operation_type == "transaction_failed":
            self.stats["transactions_failed"] += 1
        elif operation_type == "customer_failed":
            self.stats["customers_failed"] += 1
        elif operation_type == "supplier_failed":
            self.stats["suppliers_failed"] += 1
        elif operation_type == "journal_entry_failed":
            self.stats["journal_entries_failed"] += 1
        elif operation_type == "payment_entry_failed":
            self.stats["payment_entries_failed"] += 1
        
        # Normalize error message for grouping
        normalized_error = self._normalize_error(error_message)
        
        # Count this error type
        self.error_counts[normalized_error] += 1
        
        # Keep sample details (first 5 occurrences)
        if len(self.error_samples[normalized_error]) < 5:
            self.error_samples[normalized_error].append({
                "operation": operation_type,
                "error": error_message,
                "details": details,
                "time": datetime.now().strftime("%H:%M:%S")
            })
    
    def _normalize_error(self, error_message):
        """Normalize error message for grouping similar errors"""
        # Remove specific IDs, names, etc. to group similar errors
        import re
        
        # Remove quoted strings
        normalized = re.sub(r'"[^"]*"', '""', error_message)
        normalized = re.sub(r"'[^']*'", "''", normalized)
        
        # Remove numbers (IDs, amounts, etc.)
        normalized = re.sub(r'\b\d+\b', '#', normalized)
        
        # Remove specific account codes
        normalized = re.sub(r'\b\d{4,5}\b', 'XXXXX', normalized)
        
        # Truncate very long errors
        if len(normalized) > 200:
            normalized = normalized[:200] + "..."
        
        return normalized
    
    def get_summary(self):
        """Get a comprehensive summary of the migration"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        summary = {
            "duration_seconds": duration,
            "statistics": self.stats,
            "total_operations": sum(v for k, v in self.stats.items() if "created" in k),
            "total_failures": sum(v for k, v in self.stats.items() if "failed" in k),
            "unique_error_types": len(self.error_counts),
            "error_summary": []
        }
        
        # Add error summary sorted by frequency
        for error_type, count in sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True):
            error_info = {
                "error_type": error_type,
                "count": count,
                "samples": self.error_samples.get(error_type, [])
            }
            summary["error_summary"].append(error_info)
        
        return summary
    
    def get_formatted_summary(self):
        """Get a human-readable formatted summary"""
        summary = self.get_summary()
        
        lines = []
        lines.append("=" * 60)
        lines.append("E-BOEKHOUDEN MIGRATION SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Duration: {summary['duration_seconds']:.1f} seconds")
        lines.append("")
        
        # Statistics
        lines.append("STATISTICS:")
        lines.append("-" * 40)
        
        if self.stats["accounts_created"] or self.stats["accounts_updated"]:
            lines.append(f"Accounts: {self.stats['accounts_created']} created, "
                        f"{self.stats['accounts_updated']} updated, "
                        f"{self.stats['accounts_failed']} failed")
        
        if self.stats["transactions_created"]:
            lines.append(f"Transactions: {self.stats['transactions_created']} created, "
                        f"{self.stats['transactions_failed']} failed")
        
        if self.stats["journal_entries_created"]:
            lines.append(f"Journal Entries: {self.stats['journal_entries_created']} created, "
                        f"{self.stats['journal_entries_failed']} failed")
        
        if self.stats["payment_entries_created"]:
            lines.append(f"Payment Entries: {self.stats['payment_entries_created']} created, "
                        f"{self.stats['payment_entries_failed']} failed")
        
        if self.stats["customers_created"]:
            lines.append(f"Customers: {self.stats['customers_created']} created, "
                        f"{self.stats['customers_failed']} failed")
        
        if self.stats["suppliers_created"]:
            lines.append(f"Suppliers: {self.stats['suppliers_created']} created, "
                        f"{self.stats['suppliers_failed']} failed")
        
        lines.append("")
        lines.append(f"TOTAL: {summary['total_operations']} successful, "
                    f"{summary['total_failures']} failed")
        
        # Error summary
        if summary["error_summary"]:
            lines.append("")
            lines.append("ERROR SUMMARY:")
            lines.append("-" * 40)
            
            for i, error_info in enumerate(summary["error_summary"][:10]):  # Show top 10
                lines.append(f"\n{i+1}. Error occurred {error_info['count']} time(s):")
                lines.append(f"   {error_info['error_type']}")
                
                if error_info["samples"]:
                    lines.append("   Examples:")
                    for sample in error_info["samples"][:2]:  # Show 2 examples
                        lines.append(f"   - {sample['time']}: {sample['error']}")
                        if sample.get("details"):
                            lines.append(f"     Details: {sample['details']}")
            
            if len(summary["error_summary"]) > 10:
                lines.append(f"\n... and {len(summary['error_summary']) - 10} more error types")
        
        return "\n".join(lines)
    
    def save_to_log(self):
        """Save the summary to Frappe error log"""
        summary = self.get_formatted_summary()
        
        # Only log to error log if there were actual errors
        if self.get_summary()["total_failures"] > 0:
            frappe.log_error(
                title=f"E-Boekhouden Migration Summary - {self.migration_name}",
                message=summary
            )
        
        return summary