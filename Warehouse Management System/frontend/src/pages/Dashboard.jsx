import { useState, useEffect } from 'react'
import {
  Box, Card, CardContent, Typography, Grid, CircularProgress, Alert, Button,
} from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import api from '../api'
import { useRobotContext } from '../contexts/RobotContext'

function timeAgo(dateStr) {
  if (!dateStr) return '-'
  const diff = Date.now() - new Date(dateStr).getTime()
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

const statusColors = {
  ONLINE: '#4caf50',
  OFFLINE: '#f44336',
  ERROR: '#ff9800',
}

const modeLabels = {
  IDLE: 'Idle',
  AUTO: 'Auto',
  MANUAL: 'Manual',
  SEMI_MANUAL: 'Semi-Manual',
  MAPPING: 'Mapping',
}

const orderStatusColors = {
  PENDING: '#2196f3',
  QUEUED_OFFLINE: '#ffeb3b',
  IN_PROGRESS: '#4caf50',
  COMPLETED: '#1b5e20',
  FAILED: '#f44336',
  CANCELLED: '#9e9e9e',
}

const robotColumns = [
  { field: 'robot_id', headerName: 'Robot ID', width: 100 },
  { field: 'name', headerName: 'Name', width: 180 },
  {
    field: 'system_status', headerName: 'Status', width: 110,
    renderCell: (params) => (
      <Box sx={{ color: statusColors[params.value] ?? '#fff', fontWeight: 'bold' }}>
        {params.value}
      </Box>
    ),
  },
  {
    field: 'operational_mode', headerName: 'Mode', width: 130,
    renderCell: (params) => modeLabels[params.value] || params.value,
  },
  { field: 'controlled_by', headerName: 'Controlled By', width: 120 },
  { field: 'current_task', headerName: 'Task', width: 80 },
  { field: 'last_seen', headerName: 'Last Seen', width: 100, renderCell: (p) => timeAgo(p.value) },
]

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [robotList, setRobotList] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { robots, updateRobot } = useRobotContext()

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, robotsRes, ordersRes] = await Promise.all([
        api.get('/dashboard/stats/'),
        api.get('/robots/'),
        api.get('/orders/?page_size=10&ordering=-created_at'),
      ])
      setStats(statsRes.data)
      setRobotList(robotsRes.data.results || robotsRes.data)
      robotsRes.data.results?.forEach((r) => updateRobot(r))
      setOrders(ordersRes.data.results || ordersRes.data)
    } catch {
      setError('Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const mergedRobotList = robotList.map((r) => ({
    ...r,
    ...robots[r.robot_id],
  }))

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', pt: 4 }}><CircularProgress /></Box>
  if (error) return <Box textAlign="center" pt={4}><Alert severity="error">{error}<Button onClick={fetchData}>Retry</Button></Alert></Box>

  return (
    <Box>
      <Grid container spacing={2} mb={3}>
        <Grid xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h4">{stats?.active_robots ?? 0}</Typography>
            <Typography color="text.secondary">Active Robots</Typography>
          </CardContent></Card>
        </Grid>
        <Grid xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h4" color="error">{stats?.error_robots ?? 0}</Typography>
            <Typography color="text.secondary">Robots in Error</Typography>
          </CardContent></Card>
        </Grid>
        <Grid xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h4">{stats?.pending_orders ?? 0}</Typography>
            <Typography color="text.secondary">Pending Orders</Typography>
          </CardContent></Card>
        </Grid>
        <Grid xs={12} sm={6} md={3}>
          <Card><CardContent>
            <Typography variant="h4" color="success.main">{stats?.completed_today ?? 0}</Typography>
            <Typography color="text.secondary">Completed Today</Typography>
          </CardContent></Card>
        </Grid>
      </Grid>

      <Typography variant="h6" gutterBottom>Robots</Typography>
      <Box mb={3}>
        <DataGrid rows={mergedRobotList} columns={robotColumns} getRowId={(r) => r.robot_id} autoHeight hideFooter />
      </Box>

      <Typography variant="h6" gutterBottom>Recent Orders</Typography>
      <DataGrid
        rows={orders}
        columns={[
          { field: 'id', headerName: 'Order #', width: 100 },
          { field: 'product_name', headerName: 'Product', width: 180 },
          { field: 'assigned_robot', headerName: 'Robot', width: 100 },
          {
            field: 'status', headerName: 'Status', width: 140,
            renderCell: (p) => (
              <Box sx={{ color: orderStatusColors[p.value] ?? '#fff', fontWeight: 'bold' }}>
                {p.value}
              </Box>
            ),
          },
          { field: 'created_at', headerName: 'Created', width: 180, renderCell: (p) => new Date(p.value).toLocaleString() },
        ]}
        getRowId={(r) => r.id}
        autoHeight
        hideFooter
      />
    </Box>
  )
}
