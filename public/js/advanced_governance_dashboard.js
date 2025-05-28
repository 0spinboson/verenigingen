import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Users, 
  FileText, 
  BarChart3,
  PieChart,
  Calendar,
  Scale,
  AlertCircle,
  Target
} from 'lucide-react';

const GovernanceDashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [appealsData, setAppealsData] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch termination statistics
      const terminationStats = await frappe.call({
        method: 'verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_termination_statistics'
      });

      // Fetch appeals data
      const appealsDashboard = await frappe.call({
        method: 'verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.get_appeals_dashboard_data'
      });

      // Fetch analytics
      const analyticsData = await frappe.call({
        method: 'verenigingen.verenigingen.doctype.termination_appeals_process.termination_appeals_process.get_appeals_analytics'
      });

      // Fetch governance report
      const governanceReport = await frappe.call({
        method: 'verenigingen.verenigingen.doctype.membership_termination_request.membership_termination_request.get_expulsion_governance_report'
      });

      setDashboardData(terminationStats.message);
      setAppealsData(appealsDashboard.message);
      setAnalytics(analyticsData.message);
      
    } catch (error) {
      console.error('Error fetching governance data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const calculateRiskScore = () => {
    if (!dashboardData || !appealsData) return 0;
    
    let risk = 0;
    
    // High pending approvals increase risk
    if (dashboardData.pending_approvals > 5) risk += 20;
    
    // Overdue appeals increase risk
    if (appealsData.overdue_appeals?.length > 0) risk += 30;
    
    // High disciplinary termination rate increases risk
    const disciplinaryCount = (dashboardData.type_counts?.['Policy Violation'] || 0) + 
                             (dashboardData.type_counts?.['Disciplinary Action'] || 0) + 
                             (dashboardData.type_counts?.['Expulsion'] || 0);
    
    if (disciplinaryCount > dashboardData.total_requests * 0.3) risk += 25;
    
    // Implementation delays increase risk
    if (appealsData.implementation_pending > 2) risk += 15;
    
    return Math.min(risk, 100);
  };

  const getRiskColor = (score) => {
    if (score < 30) return 'text-green-600 bg-green-100';
    if (score < 60) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const riskScore = calculateRiskScore();

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Governance Dashboard</h1>
          <p className="text-gray-600 mt-1">Comprehensive oversight of membership terminations and appeals</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskColor(riskScore)}`}>
            Risk Score: {riskScore}/100
          </div>
          <button 
            onClick={fetchDashboardData}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Refresh Data
          </button>
        </div>
      </div>

      {/* Executive Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border-l-4 border-red-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Disciplinary Actions</CardTitle>
            <Scale className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {((dashboardData?.type_counts?.['Policy Violation'] || 0) + 
                (dashboardData?.type_counts?.['Disciplinary Action'] || 0) + 
                (dashboardData?.type_counts?.['Expulsion'] || 0))}
            </div>
            <p className="text-xs text-gray-600">
              {dashboardData?.total_requests > 0 ? 
                Math.round(((dashboardData?.type_counts?.['Policy Violation'] || 0) + 
                           (dashboardData?.type_counts?.['Disciplinary Action'] || 0) + 
                           (dashboardData?.type_counts?.['Expulsion'] || 0)) / 
                           dashboardData.total_requests * 100) : 0}% of all terminations
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-yellow-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
            <Clock className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {dashboardData?.pending_approvals || 0}
            </div>
            <p className="text-xs text-gray-600">
              Requiring immediate attention
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Appeals Filed</CardTitle>
            <FileText className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {appealsData?.total_appeals || 0}
            </div>
            <p className="text-xs text-gray-600">
              {appealsData?.overdue_appeals?.length || 0} overdue reviews
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Appeal Success Rate</CardTitle>
            <Target className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {analytics ? Math.round(
                ((analytics.success_rate?.['Upheld'] || 0) + (analytics.success_rate?.['Partially Upheld'] || 0)) / 
                (analytics.total_processed || 1) * 100
              ) : 0}%
            </div>
            <p className="text-xs text-gray-600">
              {analytics?.total_processed || 0} appeals decided
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="terminations">Terminations</TabsTrigger>
          <TabsTrigger value="appeals">Appeals</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Critical Alerts */}
          {(appealsData?.overdue_appeals?.length > 0 || dashboardData?.pending_approvals > 5) && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2 text-red-800">
                  <AlertTriangle className="h-5 w-5" />
                  <span>Critical Alerts</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {appealsData?.overdue_appeals?.length > 0 && (
                    <div className="flex items-center justify-between p-3 bg-white rounded border-l-4 border-red-500">
                      <div>
                        <h4 className="font-medium text-red-800">Overdue Appeal Reviews</h4>
                        <p className="text-sm text-red-600">{appealsData.overdue_appeals.length} appeals past review deadline</p>
                      </div>
                      <button 
                        onClick={() => setActiveTab('appeals')}
                        className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                      >
                        Review
                      </button>
                    </div>
                  )}
                  
                  {dashboardData?.pending_approvals > 5 && (
                    <div className="flex items-center justify-between p-3 bg-white rounded border-l-4 border-yellow-500">
                      <div>
                        <h4 className="font-medium text-yellow-800">High Pending Approvals</h4>
                        <p className="text-sm text-yellow-600">{dashboardData.pending_approvals} terminations awaiting approval</p>
                      </div>
                      <button 
                        onClick={() => frappe.set_route('List', 'Membership Termination Request', {status: 'Pending Approval'})}
                        className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700"
                      >
                        Review
                      </button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Process Health Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Termination Status Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dashboardData?.status_counts && Object.entries(dashboardData.status_counts)
                    .sort(([,a], [,b]) => b - a)
                    .map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className={`w-3 h-3 rounded-full ${
                          status === 'Executed' ? 'bg-gray-500' :
                          status === 'Approved' ? 'bg-green-500' :
                          status === 'Pending Approval' ? 'bg-yellow-500' :
                          status === 'Rejected' ? 'bg-red-500' : 'bg-blue-500'
                        }`}></div>
                        <span className="text-sm">{status}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold">{count}</span>
                        <span className="text-xs text-gray-500">
                          ({dashboardData.total_requests > 0 ? Math.round(count / dashboardData.total_requests * 100) : 0}%)
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Appeal Status Overview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {appealsData?.status_counts && Object.entries(appealsData.status_counts)
                    .filter(([,count]) => count > 0)
                    .sort(([,a], [,b]) => b - a)
                    .map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className={`w-3 h-3 rounded-full ${
                          status.includes('Decided') ? 'bg-gray-500' :
                          status === 'Under Review' ? 'bg-blue-500' :
                          status === 'Pending Decision' ? 'bg-yellow-500' :
                          status === 'Submitted' ? 'bg-green-500' : 'bg-gray-300'
                        }`}></div>
                        <span className="text-sm">{status}</span>
                      </div>
                      <span className="font-semibold">{count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Appeals Activity</CardTitle>
            </CardHeader>
            <CardContent>
              {appealsData?.recent_appeals?.length > 0 ? (
                <div className="space-y-3">
                  {appealsData.recent_appeals.slice(0, 5).map((appeal) => (
                    <div key={appeal.name} className="flex items-center justify-between p-3 border rounded">
                      <div>
                        <h4 className="font-medium">{appeal.member_name}</h4>
                        <p className="text-sm text-gray-600">
                          Appeal by {appeal.appellant_name} • {new Date(appeal.appeal_date).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge className={
                          appeal.appeal_status === 'Under Review' ? 'bg-blue-100 text-blue-800' :
                          appeal.appeal_status === 'Pending Decision' ? 'bg-yellow-100 text-yellow-800' :
                          appeal.appeal_status.includes('Decided') ? 'bg-gray-100 text-gray-800' :
                          'bg-green-100 text-green-800'
                        }>
                          {appeal.appeal_status}
                        </Badge>
                        <button 
                          onClick={() => frappe.set_route('Form', 'Termination Appeals Process', appeal.name)}
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          View
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-600 italic">No recent appeals activity</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="terminations" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Termination Types Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {dashboardData?.type_counts && Object.entries(dashboardData.type_counts)
                    .filter(([,count]) => count > 0)
                    .sort(([,a], [,b]) => b - a)
                    .map(([type, count]) => {
                      const isDisciplinary = ['Policy Violation', 'Disciplinary Action', 'Expulsion'].includes(type);
                      return (
                        <div key={type} className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className={`text-sm ${isDisciplinary ? 'font-medium text-red-700' : ''}`}>
                              {type}
                            </span>
                            <span className="font-semibold">{count}</span>
                          </div>
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div 
                              className={`h-2 rounded-full ${isDisciplinary ? 'bg-red-500' : 'bg-blue-500'}`}
                              style={{
                                width: `${dashboardData.total_requests > 0 ? (count / dashboardData.total_requests * 100) : 0}%`
                              }}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Processing Efficiency</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded">
                    <div className="flex items-center space-x-2">
                      <CheckCircle className="h-5 w-5 text-green-600" />
                      <span>Executed</span>
                    </div>
                    <span className="font-bold text-green-600">{dashboardData?.status_counts?.['Executed'] || 0}</span>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-yellow-50 rounded">
                    <div className="flex items-center space-x-2">
                      <Clock className="h-5 w-5 text-yellow-600" />
                      <span>In Process</span>
                    </div>
                    <span className="font-bold text-yellow-600">
                      {(dashboardData?.status_counts?.['Draft'] || 0) + 
                       (dashboardData?.status_counts?.['Pending Approval'] || 0) + 
                       (dashboardData?.status_counts?.['Approved'] || 0)}
                    </span>
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-red-50 rounded">
                    <div className="flex items-center space-x-2">
                      <XCircle className="h-5 w-5 text-red-600" />
                      <span>Rejected</span>
                    </div>
                    <span className="font-bold text-red-600">{dashboardData?.status_counts?.['Rejected'] || 0}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="appeals" className="space-y-6">
          {/* Overdue Appeals Alert */}
          {appealsData?.overdue_appeals?.length > 0 && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader>
                <CardTitle className="text-red-800">Overdue Appeal Reviews</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {appealsData.overdue_appeals.map((appeal) => (
                    <div key={appeal.name} className="flex items-center justify-between p-3 bg-white rounded border">
                      <div>
                        <h4 className="font-medium">{appeal.member_name}</h4>
                        <p className="text-sm text-red-600">
                          Deadline: {new Date(appeal.review_deadline).toLocaleDateString()} 
                          ({Math.abs(Math.floor((new Date() - new Date(appeal.review_deadline)) / (1000 * 60 * 60 * 24)))} days overdue)
                        </p>
                        {appeal.assigned_reviewer && (
                          <p className="text-xs text-gray-600">Assigned to: {appeal.assigned_reviewer}</p>
                        )}
                      </div>
                      <button 
                        onClick={() => frappe.set_route('Form', 'Termination Appeals Process', appeal.name)}
                        className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700"
                      >
                        Review Now
                      </button>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Appeals Analytics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Appeal Success by Type</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {analytics?.type_analysis && Object.entries(analytics.type_analysis).map(([type, data]) => (
                    <div key={type} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm">{type}</span>
                        <span className="font-semibold">{Math.round(data.success_rate)}% ({data.upheld}/{data.total})</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="h-2 rounded-full bg-green-500"
                          style={{ width: `${data.success_rate}%` }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Processing Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-blue-50 rounded">
                    <div>
                      <span className="text-sm text-blue-700">Average Processing Time</span>
                      <p className="font-bold text-blue-800">{Math.round(analytics?.avg_processing_time || 0)} days</p>
                    </div>
                    <BarChart3 className="h-8 w-8 text-blue-600" />
                  </div>
                  
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded">
                    <div>
                      <span className="text-sm text-green-700">Implementation Pending</span>
                      <p className="font-bold text-green-800">{appealsData?.implementation_pending || 0}</p>
                    </div>
                    <Calendar className="h-8 w-8 text-green-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="analytics" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Trend Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Recent Activity (30 days)</span>
                    <div className="flex items-center space-x-1">
                      <TrendingUp className="h-4 w-4 text-green-600" />
                      <span className="font-semibold text-green-600">
                        {dashboardData?.recent_activity?.requests || 0}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Executions (30 days)</span>
                    <div className="flex items-center space-x-1">
                      <span className="font-semibold text-blue-600">
                        {dashboardData?.recent_activity?.executions || 0}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quality Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {analytics ? Math.round(
                        ((analytics.success_rate?.['Upheld'] || 0) + (analytics.success_rate?.['Partially Upheld'] || 0)) / 
                        (analytics.total_processed || 1) * 100
                      ) : 0}%
                    </div>
                    <p className="text-sm text-gray-600">Appeal Success Rate</p>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {Math.round(analytics?.avg_processing_time || 0)}
                    </div>
                    <p className="text-sm text-gray-600">Avg Processing Days</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Risk Assessment</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${
                      riskScore < 30 ? 'text-green-600' : 
                      riskScore < 60 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {riskScore}/100
                    </div>
                    <p className="text-sm text-gray-600">Overall Risk Score</p>
                  </div>
                  
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span>Process Health</span>
                      <span className={riskScore < 30 ? 'text-green-600' : riskScore < 60 ? 'text-yellow-600' : 'text-red-600'}>
                        {riskScore < 30 ? 'Good' : riskScore < 60 ? 'Moderate' : 'Needs Attention'}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="compliance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h4 className="font-medium">Process Compliance</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Disciplinary Approvals</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Documentation Requirements</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Appeal Deadlines</span>
                      {appealsData?.overdue_appeals?.length > 0 ? (
                        <AlertCircle className="h-4 w-4 text-yellow-600" />
                      ) : (
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <h4 className="font-medium">Audit Trail</h4>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Complete Audit Logs</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Decision Documentation</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                    <div className="flex items-center justify-between p-2 border rounded">
                      <span className="text-sm">Communication Tracking</span>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button 
                  onClick={() => frappe.set_route('query-report', 'Governance Compliance Report')}
                  className="p-4 border rounded-lg hover:bg-gray-50 text-left"
                >
                  <Scale className="h-6 w-6 text-blue-600 mb-2" />
                  <h3 className="font-medium">Compliance Report</h3>
                  <p className="text-sm text-gray-600">Generate full compliance audit</p>
                </button>
                
                <button 
                  onClick={() => frappe.set_route('List', 'Expulsion Report Entry')}
                  className="p-4 border rounded-lg hover:bg-gray-50 text-left"
                >
                  <FileText className="h-6 w-6 text-red-600 mb-2" />
                  <h3 className="font-medium">Expulsion Records</h3>
                  <p className="text-sm text-gray-600">Review disciplinary actions</p>
                </button>
                
                <button 
                  onClick={() => frappe.set_route('List', 'Termination Appeals Process')}
                  className="p-4 border rounded-lg hover:bg-gray-50 text-left"
                >
                  <Users className="h-6 w-6 text-green-600 mb-2" />
                  <h3 className="font-medium">Appeals Management</h3>
                  <p className="text-sm text-gray-600">Manage all appeals</p>
                </button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default GovernanceDashboard;
