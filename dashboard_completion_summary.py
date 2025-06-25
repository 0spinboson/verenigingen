#!/usr/bin/env python3

import frappe

@frappe.whitelist()
def get_dashboard_completion_summary():
    """Get final summary of the completed dashboard"""
    
    try:
        # Get dashboard details
        dashboard = frappe.get_doc("Dashboard", "Chapter Board Dashboard")
        
        # Get number of cards and charts
        cards = [card.card for card in dashboard.cards]
        charts = [chart.chart for chart in dashboard.charts]
        
        # Check if user has access
        user_chapters = []
        try:
            from verenigingen.templates.pages.chapter_dashboard import get_user_board_chapters
            user_chapters = get_user_board_chapters()
        except:
            pass
        
        return {
            "success": True,
            "dashboard_info": {
                "name": dashboard.dashboard_name,
                "module": dashboard.module,
                "is_standard": dashboard.is_standard,
                "creation": dashboard.creation,
                "modified": dashboard.modified
            },
            "components": {
                "cards_count": len(cards),
                "charts_count": len(charts),
                "cards": cards,
                "charts": charts
            },
            "access_info": {
                "current_user": frappe.session.user,
                "user_roles": frappe.get_roles(),
                "has_board_access": len(user_chapters) > 0,
                "board_chapters": user_chapters
            },
            "urls": {
                "desktop": "https://dev.veganisme.net/app/dashboard-view/Chapter%20Board%20Dashboard",
                "mobile": "https://dev.veganisme.net/app/dashboard-view/Chapter%20Board%20Dashboard",
                "direct_link": "/app/dashboard-view/Chapter%20Board%20Dashboard"
            },
            "navigation_instructions": [
                "1. Go to https://dev.veganisme.net",
                "2. Login with your credentials", 
                "3. Navigate to Desk > Dashboard menu",
                "4. Click on 'Chapter Board Dashboard'",
                "OR",
                "5. Use direct URL: https://dev.veganisme.net/app/dashboard-view/Chapter%20Board%20Dashboard"
            ],
            "features": [
                "Real-time chapter metrics via number cards",
                "Visual charts for member data analysis",
                "Board member access control", 
                "Multi-chapter support for board members",
                "Native Frappe dashboard UI",
                "Mobile responsive design",
                "Auto-refreshing data"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    frappe.init(site='dev.veganisme.net')
    frappe.connect()
    result = get_dashboard_completion_summary()
    print("Dashboard Summary:", result)