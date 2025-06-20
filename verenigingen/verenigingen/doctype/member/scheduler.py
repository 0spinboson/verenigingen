import frappe
from frappe import _
from frappe.utils import now
from frappe.utils.background_jobs import enqueue
import traceback


def refresh_all_member_financial_histories():
    """
    Scheduled task to refresh payment, subscription, and invoice histories for all members.
    Runs twice daily (morning and evening) to keep member financial data up-to-date.
    
    This replicates the functionality of the "Refresh Financial History" button
    for all members with customer records.
    """
    from frappe.utils import now_datetime, get_datetime
    import datetime
    
    # Check if we should run twice daily
    current_time = now_datetime()
    current_hour = current_time.hour
    
    # Get the last run time from settings
    last_run_str = frappe.db.get_single_value("Verenigingen Settings", "last_member_history_refresh")
    
    should_run = False
    run_reason = ""
    
    if not last_run_str:
        # First time running
        should_run = True
        run_reason = "First run"
    else:
        try:
            last_run = get_datetime(last_run_str)
            hours_since_last_run = (current_time - last_run).total_seconds() / 3600
            
            # Run if it's been more than 10 hours since last run
            # This ensures we run twice daily but not too frequently
            if hours_since_last_run >= 10:
                # Prefer morning (6-10 AM) or evening (6-10 PM) runs
                if (6 <= current_hour <= 10) or (18 <= current_hour <= 22):
                    should_run = True
                    run_reason = f"Scheduled run (last run {hours_since_last_run:.1f} hours ago)"
                elif hours_since_last_run >= 24:
                    # Force run if it's been more than 24 hours regardless of time
                    should_run = True
                    run_reason = f"Forced run (last run {hours_since_last_run:.1f} hours ago)"
        except Exception as e:
            # If there's an error parsing the date, run anyway
            should_run = True
            run_reason = f"Error parsing last run time: {str(e)}"
    
    if not should_run:
        frappe.logger().info(f"Skipping member history refresh - last run was recent (current hour: {current_hour})")
        return {"success": True, "message": "Skipped - ran recently", "skipped": True}
    
    frappe.logger().info(f"Starting scheduled member financial history refresh - {run_reason}")
    
    try:
        # Get all members with customer records (only these need financial history updates)
        members = frappe.get_all(
            "Member",
            filters={
                "customer": ["!=", ""],
                "docstatus": ["!=", 2]  # Exclude cancelled members
            },
            fields=["name", "full_name", "customer"]
        )
        
        if not members:
            frappe.logger().info("No members with customer records found")
            return {"success": True, "message": "No members to process", "processed": 0}
        
        frappe.logger().info(f"Found {len(members)} members to process")
        
        # For large datasets, use background jobs to avoid timeout
        if len(members) > 100:
            result = enqueue_member_history_refresh(members)
        else:
            # Process smaller datasets synchronously
            result = process_member_history_batch(members)
        
        # Update the last run time if successful
        if result and result.get("success"):
            try:
                frappe.db.set_single_value("Verenigingen Settings", "last_member_history_refresh", current_time)
                frappe.db.commit()
                frappe.logger().info("Updated last member history refresh time")
            except Exception as e:
                frappe.logger().warning(f"Could not update last run time: {str(e)}")
        
        # Add run reason to result
        if result and isinstance(result, dict):
            result["run_reason"] = run_reason
        
        return result
        
    except Exception as e:
        error_msg = f"Fatal error in scheduled member history refresh: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.logger().error(traceback.format_exc())
        return {"success": False, "message": error_msg}


def process_member_history_batch(members):
    """
    Process a batch of members for financial history refresh.
    """
    success_count = 0
    error_count = 0
    errors = []
    
    for member_data in members:
        try:
            # Get the member document
            member = frappe.get_doc("Member", member_data.name)
            
            # Use the mixin method for consistency
            result = member.refresh_financial_history()
            
            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
                errors.append(f"Member {member_data.name}: {result.get('message', 'Unknown error')}")
            
            # Log progress every 50 members
            if success_count % 50 == 0:
                frappe.logger().info(f"Processed {success_count} members successfully")
                
        except Exception as e:
            error_count += 1
            error_msg = f"Error processing member {member_data.name} ({member_data.full_name}): {str(e)}"
            errors.append(error_msg)
            frappe.logger().error(error_msg)
            
            # Continue with next member instead of failing the entire job
            continue
    
    # Log final results
    result_message = f"Member financial history refresh completed: {success_count} successful, {error_count} errors"
    frappe.logger().info(result_message)
    
    if error_count > 0:
        frappe.logger().warning(f"Errors occurred during member history refresh: {errors[:5]}")  # Log first 5 errors
    
    return {
        "success": True,
        "message": result_message,
        "processed": success_count,
        "errors": error_count,
        "total": len(members),
        "error_details": errors if error_count <= 10 else errors[:10]  # Limit error details
    }


@frappe.whitelist()
def enqueue_member_history_refresh(members=None):
    """
    Enqueue member financial history refresh as a background job for large datasets.
    """
    if members is None:
        # Get all members if not provided
        members = frappe.get_all(
            "Member",
            filters={
                "customer": ["!=", ""],
                "docstatus": ["!=", 2]
            },
            fields=["name", "full_name", "customer"]
        )
    
    return enqueue(
        process_member_history_batch,
        queue="long",
        timeout=3600,  # 1 hour timeout for large datasets
        job_name="refresh_member_financial_histories",
        members=members
    )


@frappe.whitelist()
def refresh_specific_member_histories(member_names):
    """
    Refresh financial history for specific members.
    
    Args:
        member_names: List of member names or single member name
    """
    if isinstance(member_names, str):
        member_names = [member_names]
    
    frappe.logger().info(f"Starting targeted member history refresh for {len(member_names)} members")
    
    members = []
    for member_name in member_names:
        try:
            member_data = frappe.get_value("Member", member_name, ["name", "full_name", "customer"], as_dict=True)
            if member_data and member_data.customer:
                members.append(member_data)
        except Exception as e:
            frappe.logger().error(f"Error getting member data for {member_name}: {str(e)}")
    
    if not members:
        return {"success": False, "message": "No valid members with customer records found"}
    
    return process_member_history_batch(members)


@frappe.whitelist()
def get_member_history_refresh_status():
    """
    Get status information about the member history refresh process.
    Useful for monitoring and debugging.
    """
    try:
        # Get total number of members with customer records
        total_members = frappe.db.count(
            "Member",
            filters={
                "customer": ["!=", ""],
                "docstatus": ["!=", 2]
            }
        )
        
        # Get members that have payment history
        members_with_history = frappe.db.sql("""
            SELECT COUNT(DISTINCT parent) as count
            FROM `tabMember Payment History`
            WHERE parenttype = 'Member'
        """)[0][0] if frappe.db.exists("DocType", "Member Payment History") else 0
        
        # Get recent activity
        recent_updates = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabMember Payment History`
            WHERE parenttype = 'Member'
            AND modified >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """)[0][0] if frappe.db.exists("DocType", "Member Payment History") else 0
        
        return {
            "total_members_with_customers": total_members,
            "members_with_payment_history": members_with_history,
            "recent_updates_24h": recent_updates,
            "last_refresh_time": now(),
            "coverage_percentage": round((members_with_history / total_members * 100), 2) if total_members > 0 else 0
        }
        
    except Exception as e:
        frappe.logger().error(f"Error getting member history refresh status: {str(e)}")
        return {"error": str(e)}


@frappe.whitelist()
def test_member_history_refresh(member_name=None):
    """
    Test the member history refresh functionality with a single member.
    If no member_name provided, uses the first available member with a customer record.
    """
    if not member_name:
        # Find a test member
        test_members = frappe.get_all(
            "Member",
            filters={
                "customer": ["!=", ""],
                "docstatus": ["!=", 2]
            },
            fields=["name", "full_name"],
            limit=1
        )
        
        if not test_members:
            return {"success": False, "message": "No members with customer records found for testing"}
        
        member_name = test_members[0].name
    
    try:
        member = frappe.get_doc("Member", member_name)
        
        # Record initial state
        initial_payment_history_count = len(member.payment_history) if hasattr(member, 'payment_history') else 0
        
        # Perform refresh using the mixin method
        result = member.refresh_financial_history()
        
        # Record final state
        final_payment_history_count = len(member.payment_history) if hasattr(member, 'payment_history') else 0
        
        test_result = {
            "success": result.get("success", False),
            "message": f"Test refresh completed for member {member_name}",
            "member_name": member_name,
            "member_full_name": member.full_name,
            "initial_payment_history_count": initial_payment_history_count,
            "final_payment_history_count": final_payment_history_count,
            "history_updated": final_payment_history_count != initial_payment_history_count,
            "refresh_result": result
        }
        
        return test_result
        
    except Exception as e:
        error_msg = f"Test refresh failed for member {member_name}: {str(e)}"
        frappe.logger().error(error_msg)
        return {"success": False, "message": error_msg}


def update_all_membership_durations():
    """
    Scheduled task to update membership duration calculations for all members.
    Runs daily to keep duration data current for filtering and reporting.
    """
    from frappe.utils import now_datetime
    import datetime
    
    frappe.logger().info("Starting scheduled membership duration updates")
    
    try:
        # Get all active members (exclude cancelled)
        members = frappe.get_all(
            "Member",
            filters={
                "docstatus": ["!=", 2],  # Exclude cancelled members
                "status": ["not in", ["Deceased", "Banned"]]  # Exclude inactive statuses
            },
            fields=["name", "full_name", "total_membership_days", "last_duration_update"]
        )
        
        if not members:
            frappe.logger().info("No members found for duration update")
            return {"success": True, "message": "No members to process", "processed": 0}
        
        frappe.logger().info(f"Found {len(members)} members to process")
        
        # Process in batches to avoid memory issues
        batch_size = 100
        total_processed = 0
        total_updated = 0
        errors = []
        
        for i in range(0, len(members), batch_size):
            batch = members[i:i + batch_size]
            
            for member_data in batch:
                try:
                    # Get the member document
                    member = frappe.get_doc("Member", member_data.name)
                    
                    # Calculate new duration
                    new_total_days = member.calculate_total_membership_days()
                    old_total_days = getattr(member, 'total_membership_days', 0) or 0
                    
                    # Only update if the value has changed or if it's never been set
                    if new_total_days != old_total_days or not member_data.last_duration_update:
                        member.total_membership_days = new_total_days
                        member.last_duration_update = now()
                        member.calculate_cumulative_membership_duration()
                        
                        # Save without triggering full validation to avoid recursive calls
                        member.save(ignore_permissions=True)
                        total_updated += 1
                        
                        if total_updated % 50 == 0:
                            frappe.logger().info(f"Updated {total_updated} member durations")
                    
                    total_processed += 1
                        
                except Exception as e:
                    error_msg = f"Error updating duration for member {member_data.name}: {str(e)}"
                    errors.append(error_msg)
                    frappe.logger().error(error_msg)
                    continue
            
            # Commit after each batch to avoid long transactions
            frappe.db.commit()
        
        # Log final results
        result_message = f"Membership duration update completed: {total_updated} updated out of {total_processed} processed"
        frappe.logger().info(result_message)
        
        if errors:
            frappe.logger().warning(f"Errors occurred during duration updates: {errors[:5]}")  # Log first 5 errors
        
        return {
            "success": True,
            "message": result_message,
            "processed": total_processed,
            "updated": total_updated,
            "errors": len(errors),
            "error_details": errors if len(errors) <= 10 else errors[:10]
        }
        
    except Exception as e:
        error_msg = f"Fatal error in scheduled membership duration update: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.logger().error(traceback.format_exc())
        return {"success": False, "message": error_msg}


@frappe.whitelist()
def update_single_member_duration(member_name):
    """Update duration for a single member - useful for testing"""
    try:
        member = frappe.get_doc("Member", member_name)
        result = member.update_membership_duration()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_duration_update_stats():
    """Get statistics about membership duration updates"""
    try:
        # Count members with/without duration data
        total_members = frappe.db.count("Member", filters={"docstatus": ["!=", 2]})
        
        members_with_duration = frappe.db.count(
            "Member", 
            filters={
                "docstatus": ["!=", 2],
                "total_membership_days": [">", 0]
            }
        )
        
        members_updated_today = frappe.db.count(
            "Member",
            filters={
                "docstatus": ["!=", 2],
                "last_duration_update": [">=", frappe.utils.today()]
            }
        )
        
        return {
            "total_members": total_members,
            "members_with_duration": members_with_duration,
            "members_updated_today": members_updated_today,
            "coverage_percentage": round((members_with_duration / total_members * 100), 2) if total_members > 0 else 0
        }
        
    except Exception as e:
        return {"error": str(e)}


def setup_member_scheduler_events():
    """Set up the scheduler events for member automation"""
    return {
        "daily": [
            "verenigingen.verenigingen.doctype.member.scheduler.refresh_all_member_financial_histories",
            "verenigingen.verenigingen.doctype.member.scheduler.update_all_membership_durations"
        ]
    }