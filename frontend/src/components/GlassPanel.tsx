import React from 'react';
import { motion } from 'framer-motion';

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  animate?: boolean;
  onClick?: () => void;
}

export const GlassPanel: React.FC<GlassPanelProps> = ({ 
  children, 
  className = '', 
  style,
  animate = true,
  onClick
}) => {
  if (!animate) {
    return (
      <div className={`glass-panel ${className}`} style={style} onClick={onClick}>
        {children}
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={`glass-panel ${className}`}
      style={style}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );
};
