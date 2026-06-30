import { useState, useEffect } from 'react'
import {
  Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Select, MenuItem, FormControl, InputLabel, CircularProgress, Alert,
} from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import api from '../api'

function ProductsSection({ onRefresh }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [addDialog, setAddDialog] = useState(false)
  const [editDialog, setEditDialog] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [sku, setSku] = useState('')
  const [name, setName] = useState('')

  const fetchProducts = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/products/')
      setProducts(res.data.results || res.data)
    } catch {
      setError('Failed to load products')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchProducts() }, [])

  const handleAdd = async () => {
    try {
      await api.post('/products/', { sku, name })
      setAddDialog(false)
      setSku('')
      setName('')
      fetchProducts()
      if (onRefresh) onRefresh()
    } catch (err) {
      alert(err.response?.data?.error || 'Error creating product')
    }
  }

  const handleEdit = async () => {
    if (!editDialog) return
    try {
      await api.put(`/products/${editDialog.sku}/`, { name: editDialog.name })
      setEditDialog(null)
      fetchProducts()
    } catch {}
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await api.delete(`/products/${deleteConfirm}/`)
      setDeleteConfirm(null)
      fetchProducts()
    } catch (err) {
      if (err.response?.status === 409) alert('Cannot delete product with order history')
    }
  }

  if (loading) return <CircularProgress />
  if (error) return <Alert severity="error">{error}<Button onClick={fetchProducts}>Retry</Button></Alert>

  return (
    <Box mb={4}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6">Products</Typography>
        <Button variant="contained" onClick={() => setAddDialog(true)}>+ Add Product</Button>
      </Box>
      <DataGrid
        rows={products}
        columns={[
          { field: 'sku', headerName: 'SKU', width: 150 },
          { field: 'name', headerName: 'Name', width: 250 },
          { field: 'positions_count', headerName: 'Positions', width: 100 },
          { field: 'updated_at', headerName: 'Updated', width: 180, renderCell: (p) => new Date(p.value).toLocaleString() },
          {
            field: 'actions', headerName: 'Actions', width: 150,
            renderCell: (p) => (
              <Box>
                <Button size="small" onClick={() => setEditDialog({ sku: p.row.sku, name: p.row.name })}>Edit</Button>
                <Button size="small" color="error" onClick={() => setDeleteConfirm(p.row.sku)}>Delete</Button>
              </Box>
            ),
          },
        ]}
        getRowId={(r) => r.sku}
        autoHeight
        hideFooter
      />
      <Dialog open={addDialog} onClose={() => setAddDialog(false)}>
        <DialogTitle>Add Product</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="SKU" value={sku} onChange={(e) => setSku(e.target.value)} margin="normal" />
          <TextField fullWidth label="Name" value={name} onChange={(e) => setName(e.target.value)} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAdd}>Create</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(editDialog)} onClose={() => setEditDialog(null)}>
        <DialogTitle>Edit Product</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="Name" value={editDialog?.name || ''} onChange={(e) => setEditDialog((p) => p ? { ...p, name: e.target.value } : null)} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>Cancel</Button>
          <Button onClick={handleEdit}>Save</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(deleteConfirm)} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Product</DialogTitle>
        <DialogContent>Are you sure?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button color="error" onClick={handleDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

function PositionsSection() {
  const [maps, setMaps] = useState([])
  const [selectedMap, setSelectedMap] = useState('')
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(true)
  const [addDialog, setAddDialog] = useState(false)
  const [editDialog, setEditDialog] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [newProduct, setNewProduct] = useState('')
  const [newX, setNewX] = useState(0)
  const [newY, setNewY] = useState(0)
  const [productsForSelect, setProductsForSelect] = useState([])

  const fetchMaps = async () => {
    try {
      const res = await api.get('/maps/')
      const mapList = res.data.results || res.data
      setMaps(mapList)
      if (mapList.length > 0 && !selectedMap) {
        const active = mapList.find((m) => m.is_active)
        setSelectedMap(active ? active.id : mapList[0].id)
      }
    } catch {}
  }

  const fetchPositions = async () => {
    if (!selectedMap) return
    setLoading(true)
    try {
      const [posRes, prodRes] = await Promise.all([
        api.get(`/product-positions/?map=${selectedMap}`),
        api.get('/products/'),
      ])
      setPositions(posRes.data.results || posRes.data)
      setProductsForSelect(prodRes.data.results || prodRes.data)
    } catch {
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchMaps() }, [])
  useEffect(() => { fetchPositions() }, [selectedMap])

  const handleAdd = async () => {
    try {
      await api.post('/product-positions/', { product_sku: newProduct, map_id: parseInt(selectedMap), pos_x: newX, pos_y: newY })
      setAddDialog(false)
      setNewProduct('')
      setNewX(0)
      setNewY(0)
      fetchPositions()
    } catch (err) {
      alert(err.response?.data?.error || 'Error')
    }
  }

  const handleEdit = async () => {
    if (!editDialog) return
    try {
      await api.put(`/product-positions/${editDialog.id}/`, { pos_x: editDialog.pos_x, pos_y: editDialog.pos_y })
      setEditDialog(null)
      fetchPositions()
    } catch {}
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await api.delete(`/product-positions/${deleteConfirm}/`)
      setDeleteConfirm(null)
      fetchPositions()
    } catch {}
  }

  const usedProductSkus = new Set(positions.map((p) => p.product_sku))
  const availableProducts = productsForSelect.filter((p) => !usedProductSkus.has(p.sku))

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="h6">Product Positions</Typography>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Map</InputLabel>
          <Select value={selectedMap} onChange={(e) => setSelectedMap(e.target.value)}>
            {maps.map((m) => (
              <MenuItem key={m.id} value={m.id}>{m.name}{m.is_active ? ' (Active)' : ''}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
      {!selectedMap ? (
        <Alert severity="info">No maps available</Alert>
      ) : loading ? (
        <CircularProgress />
      ) : (
        <>
          <Button variant="contained" onClick={() => setAddDialog(true)} sx={{ mb: 2 }}>+ Add Position</Button>
          <DataGrid
            rows={positions}
            columns={[
              { field: 'product_sku', headerName: 'SKU', width: 150 },
              { field: 'product_name', headerName: 'Name', width: 200 },
              { field: 'pos_x', headerName: 'X (m)', width: 100 },
              { field: 'pos_y', headerName: 'Y (m)', width: 100 },
              {
                field: 'actions', headerName: 'Actions', width: 150,
                renderCell: (p) => (
                  <Box>
                    <Button size="small" onClick={() => setEditDialog({ id: p.row.id, pos_x: p.row.pos_x, pos_y: p.row.pos_y })}>Edit</Button>
                    <Button size="small" color="error" onClick={() => setDeleteConfirm(p.row.id)}>Delete</Button>
                  </Box>
                ),
              },
            ]}
            getRowId={(r) => r.id}
            autoHeight
            hideFooter
          />
        </>
      )}
      <Dialog open={addDialog} onClose={() => setAddDialog(false)}>
        <DialogTitle>Add Position</DialogTitle>
        <DialogContent>
          <FormControl fullWidth margin="normal">
            <InputLabel>Product</InputLabel>
            <Select label="Product" value={newProduct} onChange={(e) => setNewProduct(e.target.value)}>
              {availableProducts.map((p) => (
                <MenuItem key={p.sku} value={p.sku}>{p.sku} - {p.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField fullWidth label="X (meters)" type="number" value={newX} onChange={(e) => setNewX(parseFloat(e.target.value))} margin="normal" />
          <TextField fullWidth label="Y (meters)" type="number" value={newY} onChange={(e) => setNewY(parseFloat(e.target.value))} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAdd}>Create</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(editDialog)} onClose={() => setEditDialog(null)}>
        <DialogTitle>Edit Position</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="X (meters)" type="number" value={editDialog?.pos_x || 0} onChange={(e) => setEditDialog((p) => p ? { ...p, pos_x: parseFloat(e.target.value) } : null)} margin="normal" />
          <TextField fullWidth label="Y (meters)" type="number" value={editDialog?.pos_y || 0} onChange={(e) => setEditDialog((p) => p ? { ...p, pos_y: parseFloat(e.target.value) } : null)} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>Cancel</Button>
          <Button onClick={handleEdit}>Save</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(deleteConfirm)} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Position</DialogTitle>
        <DialogContent>Are you sure?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button color="error" onClick={handleDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default function Inventory() {
  return (
    <Box>
      <ProductsSection />
      <PositionsSection />
    </Box>
  )
}
