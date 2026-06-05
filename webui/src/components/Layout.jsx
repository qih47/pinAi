import React from 'react';
import { Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div style={styles.globalContainer}>
      <style>{`
        body, html {
          margin: 0;
          padding: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: #151517;
        }
        * {
          box-sizing: border-box;
        }
      `}</style>
      <Outlet />
    </div>
  );
}

const styles = {
  globalContainer: {
    width: '100vw',
    height: '100vh',
    overflow: 'hidden',
    position: 'relative'
  }
};