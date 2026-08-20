import React, { useEffect, useRef, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin, Globe } from 'lucide-react';
import { renderToString } from 'react-dom/server';
import ViewerHeader from './ViewerHeader';

export default function MapViewer({ chartCode, darkMode }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const exportRef = useRef(null);
  const mapContainer = useRef(null);
  const mapInstance = useRef(null);

  // Parse JSON Map dari LLM (berisi title, center, zoom, markers)
  const parsedData = useMemo(() => {
    try {
      const cleaned = (chartCode || '').replace(/```map/g, '').replace(/```/g, '').trim();
      return JSON.parse(cleaned);
    } catch (e) {
      return null;
    }
  }, [chartCode]);

  // Kita rakit murni OSM Raster Style secara manual agar terbebas dari blokir CORS CartoDB
  const mapStyleObj = useMemo(() => ({
    version: 8,
    sources: {
      'osm-tiles': {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors',
        maxzoom: 19
      }
    },
    layers: [
      {
        id: 'osm-layer',
        type: 'raster',
        source: 'osm-tiles',
        minzoom: 0,
        maxzoom: 24
      }
    ]
  }), []);

  useEffect(() => {
    if (!parsedData || !parsedData.center || !mapContainer.current) return;

    // Inisialisasi MapLibre Native
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: mapStyleObj,
      center: [parsedData.center[1], parsedData.center[0]], // [lng, lat]
      zoom: parsedData.zoom || 14,
      pitch: 45, // Otomatis miring 3D
      bearing: 0,
      attributionControl: false,
      preserveDrawingBuffer: true // Penting agar bisa di-export ke PNG (html2canvas)
    });

    mapInstance.current = map;

    // Tambahkan tombol navigasi kompas 3D
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

    // Mencegah bug kanvas map kepotong (tinggi setengah) saat pertama kali dirender React
    map.on('load', () => {
      map.resize();
      setTimeout(() => map.resize(), 200);
      
      // Mengaktifkan fitur Animasi Rotasi Otomatis (Cinematic Orbit)
      let isUserInteracting = false;
      const stopOrbit = () => { isUserInteracting = true; };
      
      map.on('mousedown', stopOrbit);
      map.on('touchstart', stopOrbit);
      map.on('dragstart', stopOrbit);
      map.on('zoomstart', stopOrbit);

      const rotateCamera = () => {
        if (isUserInteracting || !map) return;
        // Memutar kamera 0.15 derajat di setiap frame secara halus
        map.setBearing(map.getBearing() + 0.15);
        requestAnimationFrame(rotateCamera);
      };
      
      rotateCamera(); // Eksekusi rotasi!
    });

    // Render Markers
    if (parsedData.markers) {
      parsedData.markers.forEach((markerInfo) => {
        // Buat elemen kustom untuk marker
        const el = document.createElement('div');
        el.className = 'relative group cursor-pointer flex flex-col items-center justify-center';
        
        // Komponen Marker HTML
        const markerHtml = `
          <div class="relative w-6 h-6 bg-blue-500 rounded-full animate-ping opacity-75 absolute"></div>
          <div class="relative bg-blue-600 rounded-full p-1 border-2 border-white shadow-md z-0 flex items-center justify-center w-8 h-8">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
          </div>
        `;
        el.innerHTML = markerHtml;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([markerInfo.position[1], markerInfo.position[0]])
          .addTo(map);

        // Tambahkan Popup jika ada (teks dipaksa abu-abu gelap agar tidak nyaru sama putih)
        if (markerInfo.popup) {
          const popup = new maplibregl.Popup({ offset: 25, closeButton: false, className: 'custom-popup' })
            .setHTML(`<div class="font-bold text-sm px-2 py-1 text-gray-800">${markerInfo.popup}</div>`);
          marker.setPopup(popup);
          
          el.addEventListener('mouseenter', () => marker.togglePopup());
          el.addEventListener('mouseleave', () => marker.togglePopup());
        }
      });
    }

    return () => {
      map.remove();
    };
  }, [parsedData, mapStyleObj, isExpanded]);

  // Auto resize map ketika mode fullscreen toggle
  useEffect(() => {
    if (mapInstance.current) {
      setTimeout(() => mapInstance.current.resize(), 100);
      setTimeout(() => mapInstance.current.resize(), 300);
    }
  }, [isExpanded]);

  // Tampilan Loading
  if (!parsedData || !parsedData.center) {
    return (
      <div className={`my-4 w-full h-[350px] p-2 rounded-2xl border shadow-sm flex flex-col items-center justify-center animate-pulse ${darkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-gray-100 border-gray-300'}`}>
        <div className="relative w-16 h-16 rounded-full bg-blue-500/20 flex items-center justify-center mb-4">
          <MapPin className="w-8 h-8 text-blue-500 animate-bounce" />
          <div className="absolute w-full h-full rounded-full border-4 border-blue-500/30 animate-ping"></div>
        </div>
        <p className={`font-medium ${darkMode ? 'text-gray-300' : 'text-gray-600'}`}>
          Menerjemahkan Koordinat 3D...
        </p>
      </div>
    );
  }


  const content = (
    <div className={
      isExpanded 
        ? `fixed inset-0 z-[9999] p-4 md:p-10 flex flex-col ${darkMode ? 'bg-[#121212]/95 backdrop-blur-sm' : 'bg-gray-100/95 backdrop-blur-sm'}`
        : `my-4 w-full rounded-xl border shadow-sm flex flex-col ${darkMode ? 'bg-[#222225] border-gray-700/60' : 'bg-white border-gray-200'}`
    }>
      <ViewerHeader 
        title={parsedData?.title || "3D Interactive Map"} 
        icon={<Globe size={15} />} 
        onExpand={() => setIsExpanded(!isExpanded)} 
        isExpanded={isExpanded} 
        exportTargetRef={exportRef} 
        darkMode={darkMode} 
      />

      <div 
        ref={exportRef} 
        className={`flex-1 w-full flex flex-col ${darkMode ? 'bg-[#222225]' : 'bg-white'} ${isExpanded ? 'rounded-b-xl shadow-2xl border-x border-b ' + (darkMode ? 'border-gray-800' : 'border-gray-200') : 'rounded-b-xl p-2'}`}
      >
        {isExpanded && parsedData.title && (
          <h3 className={`text-lg font-bold my-4 text-center ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>
            {parsedData.title}
          </h3>
        )}
        
        <div 
          ref={mapContainer} 
          className={`relative w-full ${isExpanded ? 'flex-1 rounded-b-xl' : 'h-[380px] rounded-xl'} overflow-hidden shadow-inner bg-[#E5E3DF]`}
          style={{
            // Trik filter ajaib untuk bikin OSM jadi Dark Mode ala intelijen
            filter: darkMode ? 'invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%)' : 'none'
          }}
        />
      </div>
    </div>
  );

  return isExpanded ? createPortal(content, document.body) : content;
}
