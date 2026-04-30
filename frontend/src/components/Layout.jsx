import React from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import './Layout.css';

function Layout({ children, currentPage, setCurrentPage, health, metadata, loading }) {
  return (
    <div className="layout">
      <Header health={health} metadata={metadata} loading={loading} />
      <div className="layout-body">
        <Sidebar currentPage={currentPage} setCurrentPage={setCurrentPage} />
        <main className="layout-main">
          {children}
        </main>
      </div>
    </div>
  );
}

export default Layout;
