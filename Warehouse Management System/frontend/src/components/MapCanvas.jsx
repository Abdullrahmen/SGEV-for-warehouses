import { useRef, useEffect, useCallback } from 'react'
import { useThemeMode } from '../contexts/ThemeContext'

function lerp(a, b, t) {
  return a + (b - a) * t
}

function lerpAngle(a, b, t) {
  let diff = b - a
  while (diff > Math.PI) diff -= 2 * Math.PI
  while (diff < -Math.PI) diff += 2 * Math.PI
  return a + diff * t
}

const ROBOT_COLORS = ['#4fc3f7', '#ff8a65', '#81c784', '#ba68c8']

function getColor(index) {
  return ROBOT_COLORS[index % ROBOT_COLORS.length]
}

export default function MapCanvas({
  mapData,
  robotPositions,
  robots,
  products = [],
  showHome = true,
  highlightedRobotId = null,
  targetPosition = null,
  onMapClick = null,
  onRightClick = null,
}) {
  const { mode } = useThemeMode()
  const canvasRef = useRef(null)
  const mapImageRef = useRef(null)
  const animFrameRef = useRef(null)

  useEffect(() => {
    if (!mapData?.map_image) return
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = mapData.map_image
    img.onload = () => {
      mapImageRef.current = img
    }
  }, [mapData?.map_image])

  const metersToPx = useCallback((mx, my) => {
    if (!mapData) return { px: 0, py: 0 }
    const px = (mx - mapData.origin_x) / mapData.resolution
    const py = mapData.height_meters / mapData.resolution - (my - mapData.origin_y) / mapData.resolution
    return { px, py }
  }, [mapData])

  const pxToMeters = useCallback((px, py) => {
    if (!mapData) return { mx: 0, my: 0 }
    const mx = px * mapData.resolution + mapData.origin_x
    const my = (mapData.height_meters / mapData.resolution - py) * mapData.resolution + mapData.origin_y
    return { mx, my }
  }, [mapData])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      if (mapImageRef.current) {
        ctx.drawImage(mapImageRef.current, 0, 0, canvas.width, canvas.height)
      }

      const now = Date.now()
      const textColor = mode === 'dark' ? '#fff' : '#000'

      Object.keys(robotPositions.current).forEach((id, index) => {
        const rp = robotPositions.current[id]
        if (!rp) return

        const t = Math.min((now - rp.timestamp) / 200, 1)
        const drawnX = lerp(rp.prevX, rp.targetX, t)
        const drawnY = lerp(rp.prevY, rp.targetY, t)
        const drawnYaw = lerpAngle(rp.prevYaw, rp.targetYaw, t)

        const { px, py } = metersToPx(drawnX, drawnY)

        const isHighlighted = id === highlightedRobotId
        const size = isHighlighted ? 14 : 10
        const color = getColor(index)

        ctx.save()
        ctx.translate(px, py)
        ctx.rotate(-drawnYaw)

        ctx.beginPath()
        ctx.moveTo(size, 0)
        ctx.lineTo(-size * 0.6, -size * 0.5)
        ctx.lineTo(-size * 0.6, size * 0.5)
        ctx.closePath()
        ctx.fillStyle = color
        ctx.fill()

        if (isHighlighted) {
          ctx.strokeStyle = '#ffff00'
          ctx.lineWidth = 2
          ctx.stroke()
        }

        ctx.restore()

        ctx.fillStyle = textColor
        ctx.font = '10px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(id, px, py - size - 4)
      })

      products.forEach((p, i) => {
        const { px, py } = metersToPx(p.pos_x, p.pos_y)
        ctx.beginPath()
        ctx.arc(px, py, 5, 0, 2 * Math.PI)
        ctx.fillStyle = '#ffd54f'
        ctx.fill()
        ctx.fillStyle = textColor
        ctx.font = '9px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(p.product_name || p.product_sku, px, py - 10)
      })

      if (showHome && mapData) {
        const { px, py } = metersToPx(mapData.home_x, mapData.home_y)
        ctx.fillStyle = '#4caf50'
        ctx.fillRect(px - 8, py - 8, 16, 16)
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1
        ctx.strokeRect(px - 8, py - 8, 16, 16)
        ctx.fillStyle = textColor
        ctx.font = '10px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('Home', px, py - 14)
      }

      if (targetPosition) {
        const { px, py } = metersToPx(targetPosition.x, targetPosition.y)
        const pulse = Math.sin(now / 300) * 0.3 + 0.7
        ctx.beginPath()
        ctx.arc(px, py, 10, 0, 2 * Math.PI)
        ctx.strokeStyle = `rgba(255, 193, 7, ${pulse})`
        ctx.lineWidth = 2
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(px, py, 4, 0, 2 * Math.PI)
        ctx.fillStyle = `rgba(255, 193, 7, ${pulse})`
        ctx.fill()
      }

      animFrameRef.current = requestAnimationFrame(draw)
    }

    animFrameRef.current = requestAnimationFrame(draw)
    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
      }
    }
  }, [mapData, robotPositions, products, showHome, highlightedRobotId, targetPosition, metersToPx, mode])

  const handleClick = (e) => {
    if (!onMapClick || !mapData) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top

    if (mapImageRef.current) {
      const offscreen = document.createElement('canvas')
      offscreen.width = mapImageRef.current.width
      offscreen.height = mapImageRef.current.height
      const offCtx = offscreen.getContext('2d')
      offCtx.drawImage(mapImageRef.current, 0, 0)
      const scaleX = mapImageRef.current.width / canvasRef.current.width
      const scaleY = mapImageRef.current.height / canvasRef.current.height
      const pixel = offCtx.getImageData(px * scaleX, py * scaleY, 1, 1).data
      const brightness = (pixel[0] + pixel[1] + pixel[2]) / 3
      if (brightness <= 200) {
        return
      }
    }

    const { mx, my } = pxToMeters(px, py)
    onMapClick(mx, my)
  }

  const handleContextMenu = (e) => {
    e.preventDefault()
    if (!onRightClick || !mapData) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    const { mx, my } = pxToMeters(px, py)
    onRightClick(mx, my, e.clientX, e.clientY)
  }

  const handleMouseMove = (e) => {
    if (!onMapClick || !mapData || !mapImageRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    const px = e.clientX - rect.left
    const py = e.clientY - rect.top
    const offscreen = document.createElement('canvas')
    offscreen.width = mapImageRef.current.width
    offscreen.height = mapImageRef.current.height
    const offCtx = offscreen.getContext('2d')
    offCtx.drawImage(mapImageRef.current, 0, 0)
    const scaleX = mapImageRef.current.width / canvasRef.current.width
    const scaleY = mapImageRef.current.height / canvasRef.current.height
    const pixel = offCtx.getImageData(px * scaleX, py * scaleY, 1, 1).data
    const brightness = (pixel[0] + pixel[1] + pixel[2]) / 3
    canvasRef.current.style.cursor = brightness > 200 ? 'crosshair' : 'not-allowed'
  }

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={600}
      style={{ width: '100%', height: '100%', border: '1px solid #333', borderRadius: 4 }}
      onClick={handleClick}
      onContextMenu={handleContextMenu}
      onMouseMove={handleMouseMove}
    />
  )
}
