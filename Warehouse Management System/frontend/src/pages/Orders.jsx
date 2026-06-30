import { useState, useEffect } from 'react'
import {
  Box, Typography, Button, Card, CardContent, FormControl, InputLabel,
  Select, MenuItem, Autocomplete, TextField, Dialog, DialogTitle,
  DialogContent, DialogActions, CircularProgress, Alert, Chip,
} from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import api from '../api'
import { useWebSocket } from '../contexts/WebSocketContext'

const statusColors = {
  PENDING: '#2196f3',
  QUEUED_OFFLINE: '#ffeb3b',
  IN_PROGRESS: '#4caf50',
  COMPLETED: '#1b5e20',
  FAILED: '#f44336',
  CANCELLED: '#9e9e9e',
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [activeMap, setActiveMap] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const { subscribe } = useWebSocket()

  const fetchOrders = async () => {
    setLoading(true)
    setError(null)
    try {
      let url = `/orders/?page=${page}&page_size=${pageSize}&ordering=-created_at`
      if (statusFilter) url += `&status=${statusFilter}`
      const res = await api.get(url)
      setOrders(res.data.results || res.data)
      setTotal(res.data.count || orders.length)
    } catch {
      setError('Failed to load orders')
    } finally {
      setLoading(false)
    }
  }

  const fetchMeta = async () => {
    try {
      const [prodRes, mapRes] = await Promise.all([
        api.get('/products/'),
        api.get('/maps/active/').catch(() => null),
      ])
      setProducts(prodRes.data.results || prodRes.data)
      setActiveMap(mapRes?.data || null)
    } catch {}
  }

  useEffect(() => {
    fetchOrders()
    fetchMeta()
  }, [page, statusFilter])

  useEffect(() => {
    const unsub = subscribe('order.update', (data) => {
      fetchOrders()
    })
    return unsub
  }, [subscribe])

  const handleCreate = async () => {
    if (!selectedProduct) return
    try {
      await api.post('/orders/', { product_sku: selectedProduct.sku })
      setSelectedProduct(null)
      fetchOrders()
    } catch (err) {
      alert(err.response?.data?.error || 'Error creating order')
    }
  }

  const handleCancel = async (orderId) => {
    try {
      await api.post(`/orders/${orderId}/cancel/`)
      fetchOrders()
    } catch {}
  }

  const productsOnActiveMap = activeMap
    ? products.filter((p) => p.positions_count > 0)
    : []

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Create Order</Typography>
          {!activeMap ? (
            <Alert severity="info">Set an active map before creating orders.</Alert>
          ) : (
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <Autocomplete
                options={productsOnActiveMap}
                getOptionLabel={(p) => `${p.sku} - ${p.name}`}
                value={selectedProduct}
                onChange={(_, v) => setSelectedProduct(v)}
                renderInput={(params) => <TextField {...params} label="Product" size="small" sx={{ width: 300 }} />}
              />
              <Button variant="contained" onClick={handleCreate} disabled={!selectedProduct}>
                Create Order
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">Orders</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Status</InputLabel>
          <Select label="Status" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="PENDING">Pending</MenuItem>
            <MenuItem value="IN_PROGRESS">In Progress</MenuItem>
            <MenuItem value="COMPLETED">Completed</MenuItem>
            <MenuItem value="FAILED">Failed</MenuItem>
            <MenuItem value="CANCELLED">Cancelled</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {loading ? <CircularProgress /> : error ? <Alert severity="error">{error}<Button onClick={fetchOrders}>Retry</Button></Alert> : (
        <DataGrid
          rows={orders}
          columns={[
            { field: 'id', headerName: 'Order #', width: 100 },
            { field: 'product_sku', headerName: 'SKU', width: 120 },
            { field: 'product_name', headerName: 'Product', width: 200 },
            { field: 'assigned_robot', headerName: 'Robot', width: 100 },
            {
              field: 'status', headerName: 'Status', width: 140,
              renderCell: (p) => (
                <Chip label={p.value} size="small" sx={{ bgcolor: statusColors[p.value] || '#999', color: '#fff', fontWeight: 'bold' }} />
              ),
            },
            { field: 'created_at', headerName: 'Created', width: 180, renderCell: (p) => new Date(p.value).toLocaleString() },
            { field: 'completed_at', headerName: 'Completed', width: 180, renderCell: (p) => p.value ? new Date(p.value).toLocaleString() : '-' },
            {
              field: 'actions', headerName: 'Actions', width: 100,
              renderCell: (p) => (
                (p.row.status === 'PENDING' || p.row.status === 'IN_PROGRESS') && (
                  <Button size="small" color="error" onClick={() => handleCancel(p.row.id)}>Cancel</Button>
                )
              ),
            },
          ]}
          getRowId={(r) => r.id}
          autoHeight
          paginationMode="server"
          rowCount={total}
          page={page - 1}
          pageSize={pageSize}
          onPageChange={(p) => setPage(p + 1)}
        />
      )}
    </Box>
  )
}
