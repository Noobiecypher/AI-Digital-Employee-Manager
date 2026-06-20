import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Activity, Clock, DollarSign, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { REPORTING_API } from '../config';

export default function Dashboard() {
  const [reportData, setReportData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchReport = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${REPORTING_API}/api/report`);
      if (!response.ok) throw new Error('Failed to capture backend engine payload.');
      const data = await response.json();
      setReportData(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReport(); }, []);

  if (loading) return (
    <div className="min-h-screen flex flex-col items-center justify-center space-y-4">
      <RefreshCw className="animate-spin text-blue-500 w-12 h-12" />
      <p className="text-gray-400 font-medium">Aggregating Agent Workflows...</p>
    </div>
  );

  if (error) return (
    <div className="min-h-screen flex flex-col items-center justify-center space-y-2">
      <AlertTriangle className="text-red-500 w-12 h-12" />
      <p className="text-red-400 font-semibold">Error: {error}</p>
      <button onClick={fetchReport} className="mt-4 px-4 py-2 bg-blue-600 rounded-lg hover:bg-blue-500">Retry Fetch</button>
    </div>
  );

  const STATUS_COLORS = { Success: '#10B981', Escalated: '#F59E0B', Failed: '#EF4444' };

  return (
    <div className="p-8">
      <header className="mb-8 flex justify-between items-center border-b border-gray-800 pb-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Execution Report</h1>
          <p className="text-gray-400 mt-1">
            Log ID: <span className="text-blue-400 font-mono text-sm">{reportData.workflow_id}</span>
          </p>
        </div>
        <button onClick={fetchReport} className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm font-medium rounded-lg border border-gray-700 transition">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Success Rate</p>
            <p className="text-3xl font-bold text-white mt-2">{reportData.metrics.success_rate}</p>
          </div>
          <div className="p-3 bg-emerald-500/10 rounded-lg text-emerald-400"><Activity className="w-6 h-6" /></div>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Total Runtime</p>
            <p className="text-3xl font-bold text-white mt-2">{reportData.metrics.runtime}</p>
          </div>
          <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400"><Clock className="w-6 h-6" /></div>
        </div>
        <div className="bg-gray-900 p-6 rounded-xl border border-gray-800 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">Resource Cost</p>
            <p className="text-3xl font-bold text-white mt-2">{reportData.metrics.resource_cost}</p>
          </div>
          <div className="p-3 bg-amber-500/10 rounded-lg text-amber-400"><DollarSign className="w-6 h-6" /></div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-gray-900 p-6 rounded-xl border border-gray-800">
          <h2 className="text-xl font-semibold mb-6 text-white">Agent Sequence Flow Trace</h2>
          <div className="h-64 w-full mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reportData.charts} layout="vertical" margin={{ left: 10, right: 10 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="task_name" type="category" width={150} tick={{ fill: '#9CA3AF', fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', borderRadius: '8px' }} itemStyle={{ color: '#F3F4F6' }} />
                <Bar dataKey="id" barSize={14} radius={[0, 4, 4, 0]}>
                  {reportData.charts.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={STATUS_COLORS[entry.execution_status] || '#3B82F6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 font-medium">
                  <th className="pb-3">Task</th>
                  <th className="pb-3">Agent</th>
                  <th className="pb-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {reportData.charts.map((task) => (
                  <tr key={task.id} className="text-gray-300">
                    <td className="py-3 font-medium max-w-xs truncate">{task.task_name}</td>
                    <td className="py-3 text-gray-400">{task.assigned_agent}</td>
                    <td className="py-3 text-right">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                        task.execution_status === 'Success' ? 'bg-emerald-500/10 text-emerald-400' :
                        task.execution_status === 'Escalated' ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400'
                      }`}>{task.execution_status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-gray-900 p-6 rounded-xl border border-gray-800">
            <h2 className="text-xl font-semibold mb-4 text-white">Agent Insights</h2>
            <div className="p-4 bg-blue-950/20 border border-blue-900/50 rounded-lg text-sm text-blue-300 leading-relaxed">
              {reportData.insights?.executive_summary || "No summary available."}
            </div>
          </div>
          <div className="bg-gray-900 p-6 rounded-xl border border-gray-800">
            <h2 className="text-xl font-semibold mb-4 text-white">Recommended Actions</h2>
            <ul className="space-y-4">
              {reportData.insights?.system_actions?.map((action, i) => (
                <li key={i} className="flex gap-3 items-start text-sm text-gray-300 leading-relaxed">
                  <div className="mt-0.5 p-1 bg-amber-500/10 text-amber-400 rounded">
                    <CheckCircle className="w-4 h-4" />
                  </div>
                  <span>{action}</span>
                </li>
              )) || <li className="text-sm text-red-400">No actions returned.</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}