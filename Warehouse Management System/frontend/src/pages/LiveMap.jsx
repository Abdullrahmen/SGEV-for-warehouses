import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Box, Tabs, Tab, Typography, CircularProgress, Alert, Button, Select, MenuItem,
  FormControl, InputLabel, TextField, Dialog, DialogTitle, DialogContent,
  DialogActions, Menu,
} from '@mui/material'
import { DataGrid } from '@mui/x-data-grid'
import MapCanvas from '../components/MapCanvas'
import { useRobotContext } from '../contexts/RobotContext'
import { useWebSocket } from '../contexts/WebSocketContext'
import api from '../api'

function LiveView({ activeMap, robotPositions, robots, products, onSetHome }) {
  const [ctxMenu, setCtxMenu] = useState(null)

  const handleRightClick = useCallback((mx, my, clientX, clientY) => {
    setCtxMenu({ mx, my, clientX, clientY })
  }, [])

  const handleSetHome = async () => {
    if (!activeMap || !ctxMenu) return
    try {
      await api.put(`/maps/${activeMap.id}/`, { home_x: ctxMenu.mx, home_y: ctxMenu.my })
    } catch {}
    setCtxMenu(null)
  }

  return (
    <Box>
      <MapCanvas
        mapData={activeMap}
        robotPositions={robotPositions}
        robots={robots}
        products={products}
        showHome
        onRightClick={handleRightClick}
      />
      <Menu
        anchorReference="anchorPosition"
        anchorPosition={ctxMenu ? { top: ctxMenu.clientY, left: ctxMenu.clientX } : undefined}
        open={Boolean(ctxMenu)}
        onClose={() => setCtxMenu(null)}
      >
        <MenuItem onClick={handleSetHome}>Set as Home Position</MenuItem>
      </Menu>
    </Box>
  )
}

function MapManagement({ onStartScan }) {
  const [maps, setMaps] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editDialog, setEditDialog] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const [setActiveDialog, setSetActiveDialog] = useState(null)

  const fetchMaps = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/maps/')
      setMaps(res.data.results || res.data)
    } catch {
      setError('Failed to load maps')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchMaps() }, [])

  const handleSetActive = async (map) => {
    try {
      const preview = await api.post(`/maps/${map.id}/set_active/`, { confirm: false })
      if (preview.data.blocked) return
      setSetActiveDialog({ map, pendingCancel: preview.data.pending_cancel_count })
    } catch (err) {
      const msg = err.response?.data?.block_reason || 'Error'
      alert(msg)
    }
  }

  const confirmSetActive = async () => {
    if (!setActiveDialog) return
    try {
      await api.post(`/maps/${setActiveDialog.map.id}/set_active/`, { confirm: true })
      setSetActiveDialog(null)
      fetchMaps()
    } catch {}
  }

  const handleEdit = async () => {
    if (!editDialog) return
    try {
      await api.put(`/maps/${editDialog.id}/`, {
        name: editDialog.name,
        home_x: editDialog.home_x,
        home_y: editDialog.home_y,
      })
      setEditDialog(null)
      fetchMaps()
    } catch {}
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      await api.delete(`/maps/${deleteConfirm}/`)
      setDeleteConfirm(null)
      fetchMaps()
    } catch (err) {
      if (err.response?.status === 409) alert('Cannot delete the active map')
    }
  }

  if (loading) return <CircularProgress />
  if (error) return <Alert severity="error">{error}<Button onClick={fetchMaps}>Retry</Button></Alert>

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">Map Library</Typography>
        <Button variant="contained" onClick={onStartScan}>+ New Scan</Button>
      </Box>
      <DataGrid
        rows={maps}
        columns={[
          { field: 'name', headerName: 'Name', width: 200 },
          { field: 'resolution', headerName: 'Resolution', width: 100, renderCell: (p) => `${p.value} m/px` },
          { field: 'width_meters', headerName: 'Width', width: 80 },
          { field: 'height_meters', headerName: 'Height', width: 80 },
          { field: 'home_x', headerName: 'Home X', width: 80 },
          { field: 'home_y', headerName: 'Home Y', width: 80 },
          {
            field: 'is_active', headerName: 'Active', width: 80,
            renderCell: (p) => p.value ? '★ Active' : '',
          },
          {
            field: 'actions', headerName: 'Actions', width: 250,
            renderCell: (p) => (
              <Box>
                {!p.row.is_active && (
                  <Button size="small" onClick={() => handleSetActive(p.row)}>Set Active</Button>
                )}
                <Button size="small" onClick={() => setEditDialog({
                  id: p.row.id, name: p.row.name, home_x: p.row.home_x, home_y: p.row.home_y,
                })}>Edit</Button>
                {!p.row.is_active && (
                  <Button size="small" color="error" onClick={() => setDeleteConfirm(p.row.id)}>Delete</Button>
                )}
              </Box>
            ),
          },
        ]}
        getRowId={(r) => r.id}
        autoHeight
        hideFooter
      />

      <Dialog open={Boolean(editDialog)} onClose={() => setEditDialog(null)}>
        <DialogTitle>Edit Map</DialogTitle>
        <DialogContent>
          <TextField fullWidth label="Name" value={editDialog?.name || ''} onChange={(e) => setEditDialog((p) => p ? { ...p, name: e.target.value } : null)} margin="normal" />
          <TextField fullWidth label="Home X" type="number" value={editDialog?.home_x || 0} onChange={(e) => setEditDialog((p) => p ? { ...p, home_x: parseFloat(e.target.value) } : null)} margin="normal" />
          <TextField fullWidth label="Home Y" type="number" value={editDialog?.home_y || 0} onChange={(e) => setEditDialog((p) => p ? { ...p, home_y: parseFloat(e.target.value) } : null)} margin="normal" />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(null)}>Cancel</Button>
          <Button onClick={handleEdit}>Save</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(setActiveDialog)} onClose={() => setSetActiveDialog(null)}>
        <DialogTitle>Set Active Map</DialogTitle>
        <DialogContent>
          {setActiveDialog?.pendingCancel > 0
            ? `Changing the active map will cancel ${setActiveDialog.pendingCancel} pending orders. Are you sure?`
            : 'Set this map as active?'}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSetActiveDialog(null)}>Cancel</Button>
          <Button onClick={confirmSetActive}>Yes</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(deleteConfirm)} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Map</DialogTitle>
        <DialogContent>Are you sure you want to delete this map?</DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button color="error" onClick={handleDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

function ScanningMode({ onExit, robotPositions }) {
  const [robotsData, setRobotsData] = useState([])
  const [selectedRobot, setSelectedRobot] = useState('')
  const [mode, setMode] = useState('manual')
  const [mapName, setMapName] = useState('')
  const [scanning, setScanning] = useState(false)
  const [hasPreview, setHasPreview] = useState(false)
  const [pressedKey, setPressedKey] = useState(null)
  const canvasRef = useRef(null)
  const previewImgRef = useRef(null)
  const activeKeyRef = useRef(null)
  const intervalRef = useRef(null)
  const animFrameRef = useRef(null)
  const { robots } = useRobotContext()
  const { subscribe, sendMessage } = useWebSocket()

  const currentRobot = robots[selectedRobot]
  const isControlling = currentRobot?.controlled_by === localStorage.getItem('username')

  useEffect(() => {
    api.get('/robots/').then((res) => {
      const list = (res.data.results || res.data).filter((r) => r.system_status === 'ONLINE' && r.operational_mode === 'IDLE')
      setRobotsData(list)
    })
  }, [])

  useEffect(() => {
    const unsub = subscribe('map.preview', (data) => {
      if (data.robot_id === selectedRobot) {
        const img = new Image()
        img.onload = () => {
          previewImgRef.current = img
          setHasPreview(true)
        }
        img.src = `data:image/png;base64,${data.image_base64}`
      }
    })
    return unsub
  }, [subscribe, selectedRobot])

  const MIN_CANVAS_PX = 300

  useEffect(() => {
    let ctx = null

    const draw = () => {
      const canvas = canvasRef.current
      if (!canvas) {
        animFrameRef.current = requestAnimationFrame(draw)
        return
      }
      if (!ctx) ctx = canvas.getContext('2d', { willReadFrequently: true })

      const img = previewImgRef.current
      if (img) {
        const iw = img.naturalWidth
        const ih = img.naturalHeight
        const cw = Math.max(iw, MIN_CANVAS_PX)
        const ch = Math.max(ih, MIN_CANVAS_PX)
        if (canvas.width !== cw || canvas.height !== ch) {
          canvas.width = cw
          canvas.height = ch
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        if (iw <= MIN_CANVAS_PX && ih <= MIN_CANVAS_PX) {
          const scale = Math.min(MIN_CANVAS_PX / iw, MIN_CANVAS_PX / ih)
          const dx = (cw - iw * scale) / 2
          const dy = (ch - ih * scale) / 2
          ctx.drawImage(img, dx, dy, iw * scale, ih * scale)
        } else {
          ctx.drawImage(img, 0, 0)
        }
      }

      const rp = robotPositions.current[selectedRobot]
      if (rp && previewImgRef.current) {
        const cx = canvas.width / 2
        const cy = canvas.height / 2
        const size = 8
        ctx.save()
        ctx.translate(cx, cy)
        ctx.rotate(-rp.targetYaw)
        ctx.beginPath()
        ctx.moveTo(size, 0)
        ctx.lineTo(-size * 0.6, -size * 0.5)
        ctx.lineTo(-size * 0.6, size * 0.5)
        ctx.closePath()
        ctx.fillStyle = '#4fc3f7'
        ctx.fill()
        ctx.strokeStyle = '#ffff00'
        ctx.lineWidth = 2
        ctx.stroke()
        ctx.restore()
      }
      animFrameRef.current = requestAnimationFrame(draw)
    }

    animFrameRef.current = requestAnimationFrame(draw)
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [selectedRobot, robotPositions])

  const sendCommand = useCallback((command) => {
    if (!selectedRobot) return
    sendMessage({ type: 'cmd_manual', robot_id: selectedRobot, command })
  }, [selectedRobot, sendMessage])

  const stopMovement = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (activeKeyRef.current) {
      sendCommand('STOP')
      activeKeyRef.current = null
    }
  }, [sendCommand])

  const handleKeyDown = useCallback((e) => {
    const key = ({ KeyW: 'W', KeyA: 'A', KeyS: 'S', KeyD: 'D' })[e.code]
    if (!key || !isControlling || mode !== 'manual') return
    e.preventDefault()
    if (activeKeyRef.current === key) return
    stopMovement()
    activeKeyRef.current = key
    setPressedKey(key)
    sendCommand(key)
    intervalRef.current = setInterval(() => sendCommand(key), 100)
  }, [isControlling, sendCommand, mode])

  useEffect(() => {
    const handleKeyUp = (e) => {
      const key = ({ KeyW: 'W', KeyA: 'A', KeyS: 'S', KeyD: 'D' })[e.code]
      if (key && activeKeyRef.current === key) {
        setPressedKey(null)
        stopMovement()
      }
    }
    const handleBlur = () => {
      if (activeKeyRef.current) {
        setPressedKey(null)
        stopMovement()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('blur', handleBlur)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('blur', handleBlur)
      stopMovement()
    }
  }, [handleKeyDown, stopMovement])

  const startScan = async () => {
    if (!selectedRobot || !mapName) return
    try {
      await api.post('/maps/start_scan/', { robot_id: selectedRobot, mode, map_name: mapName })
      setScanning(true)
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to start scan')
    }
  }

  const stopScan = async () => {
    stopMovement()
    try {
      await api.post('/maps/stop_scan/', { robot_id: selectedRobot, map_name: mapName })
      alert('Save requested')
    } catch {}
  }

  const cancelScan = async () => {
    stopMovement()
    try {
      await api.post('/maps/cancel_scan/', { robot_id: selectedRobot })
    } catch {}
    setScanning(false)
    setHasPreview(false)
    onExit()
  }

  if (!scanning) {
    return (
      <Box p={2}>
        <Typography variant="h6" gutterBottom>New Scan</Typography>
        <FormControl fullWidth margin="normal">
          <InputLabel>Robot</InputLabel>
          <Select label="Robot" value={selectedRobot} onChange={(e) => setSelectedRobot(e.target.value)}>
            {robotsData.map((r) => (
              <MenuItem key={r.robot_id} value={r.robot_id}>{r.robot_id} - {r.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl fullWidth margin="normal">
          <InputLabel>Mode</InputLabel>
          <Select label="Mode" value={mode} onChange={(e) => setMode(e.target.value)}>
            <MenuItem value="manual">Manual</MenuItem>
            <MenuItem value="autonomous">Autonomous</MenuItem>
          </Select>
        </FormControl>
        <TextField fullWidth label="Map Name" value={mapName} onChange={(e) => setMapName(e.target.value)} margin="normal" />
        <Button variant="contained" onClick={startScan} disabled={!selectedRobot || !mapName}>Start Scanning</Button>
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', p: 2 }}>
        <Typography variant="h6">Scanning: {mapName}</Typography>
        <Box>
          {mode === 'manual' && (
            <Button onClick={stopScan} variant="contained" color="success" sx={{ mr: 1 }}>Save Map</Button>
          )}
          <Button onClick={cancelScan} variant="outlined" color="error">Discard & Cancel</Button>
        </Box>
      </Box>
      <Box display="flex">
        <Box flex={1} position="relative" sx={{ textAlign: 'center' }}>
          <canvas
            ref={canvasRef}
            style={{ maxWidth: '100%', minWidth: 200, minHeight: 150, imageRendering: 'pixelated' }}
          />
          {!hasPreview && (
            <Box position="absolute" top={0} left={0} right={0} bottom={0} display="flex" sx={{ alignItems: 'center', justifyContent: 'center' }}>
              <Typography>Waiting for map data...</Typography>
            </Box>
          )}
        </Box>
        {isControlling && mode === 'manual' && (
          <Box width={160} p={2} sx={{ textAlign: 'center' }}>
            <Typography variant="body2" gutterBottom>WASD</Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5 }}>
              <Button variant="contained" sx={{ minWidth: 50, height: 50, filter: pressedKey === 'W' ? 'brightness(1.3)' : 'none' }}
                onMouseDown={() => { setPressedKey('W'); sendCommand('W'); intervalRef.current = setInterval(() => sendCommand('W'), 100) }}
                onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>W</Button>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Button variant="contained" sx={{ minWidth: 50, height: 50, filter: pressedKey === 'A' ? 'brightness(1.3)' : 'none' }}
                  onMouseDown={() => { setPressedKey('A'); sendCommand('A'); intervalRef.current = setInterval(() => sendCommand('A'), 100) }}
                  onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>A</Button>
                <Button variant="contained" sx={{ minWidth: 50, height: 50, filter: pressedKey === 'S' ? 'brightness(1.3)' : 'none' }}
                  onMouseDown={() => { setPressedKey('S'); sendCommand('S'); intervalRef.current = setInterval(() => sendCommand('S'), 100) }}
                  onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>S</Button>
                <Button variant="contained" sx={{ minWidth: 50, height: 50, filter: pressedKey === 'D' ? 'brightness(1.3)' : 'none' }}
                  onMouseDown={() => { setPressedKey('D'); sendCommand('D'); intervalRef.current = setInterval(() => sendCommand('D'), 100) }}
                  onMouseUp={() => { setPressedKey(null); stopMovement() }} onMouseLeave={() => { setPressedKey(null); stopMovement() }}>D</Button>
              </Box>
            </Box>
          </Box>
        )}
        {isControlling && mode === 'autonomous' && (
          <Box width={160} p={2} sx={{ textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Typography variant="body2" color="text.secondary">Auto-Exploring</Typography>
            <Typography variant="caption" color="text.disabled">Robot scans autonomously</Typography>
          </Box>
        )}
      </Box>
    </Box>
  )
}

export default function LiveMap() {
  const [tab, setTab] = useState(0)
  const [activeMap, setActiveMap] = useState(null)
  const [products, setProducts] = useState([])
  const [scanning, setScanning] = useState(false)
  const { robotPositions, robots } = useRobotContext()

  const fetchActiveMap = async () => {
    try {
      const res = await api.get('/maps/active/')
      setActiveMap(res.data)
      const posRes = await api.get(`/product-positions/?map=${res.data.id}`)
      setProducts(posRes.data.results || posRes.data)
    } catch {
      setActiveMap(null)
    }
  }

  useEffect(() => {
    fetchActiveMap()
    const interval = setInterval(fetchActiveMap, 30000)
    return () => clearInterval(interval)
  }, [])

  if (scanning) {
    return <ScanningMode onExit={() => { setScanning(false); fetchActiveMap() }} robotPositions={robotPositions} />
  }

  return (
    <Box>
      <Tabs value={tab} onChange={(_, v) => setTab(v)}>
        <Tab label="Live View" />
        <Tab label="Map Management" />
      </Tabs>
      <Box pt={2}>
        {tab === 0 && (
          activeMap
            ? <LiveView activeMap={activeMap} robotPositions={robotPositions} robots={robots} products={products} />
            : <Alert severity="info">No active map set. Go to Map Management to scan or activate a map.</Alert>
        )}
        {tab === 1 && <MapManagement onStartScan={() => setScanning(true)} />}
      </Box>
    </Box>
  )
}
