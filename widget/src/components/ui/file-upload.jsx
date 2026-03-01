import { cn } from "@/lib/utils";
import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Upload } from "lucide-react";

const mainVariant = {
  initial: { x: 0, y: 0 },
  animate: { x: 20, y: -20, opacity: 0.9 },
};

const secondaryVariant = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
};

export const FileUpload = ({ onChange }) => {
  const [files, setFiles] = useState([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (newFiles) => {
    setFiles((prevFiles) => [...prevFiles, ...newFiles]);
    onChange && onChange(newFiles);
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFileChange(droppedFiles);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = () => {
    setIsDragActive(false);
  };

  return (
    <div 
      className="w-full" 
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {files.length === 0 && (
        <motion.div
          onClick={handleClick}
          whileHover={{ scale: 1.02 }}
          className="group/file block cursor-pointer w-full relative overflow-hidden"
          style={{
            background: 'rgba(255, 255, 255, 0.3)',
            backdropFilter: 'blur(30px)',
            WebkitBackdropFilter: 'blur(30px)',
            border: isDragActive ? '2px solid #000000' : '2px dashed rgba(0, 0, 0, 0.3)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
            borderRadius: '24px',
            aspectRatio: '1',
            maxWidth: '400px',
            margin: '0 auto'
          }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <input
            ref={fileInputRef}
            id="file-upload-handle"
            type="file"
            accept=".xml,.zip"
            onChange={(e) => handleFileChange(Array.from(e.target.files || []))}
            className="hidden"
          />
          <div className="flex flex-col items-center justify-center h-full p-8">
            <motion.div
              animate={isDragActive ? { scale: 1.1 } : { scale: 1 }}
              className="mb-6"
            >
              <Upload 
                className="w-16 h-16" 
                style={{ 
                  color: '#000000',
                  strokeWidth: 2
                }} 
              />
            </motion.div>
            <h3 className="text-2xl font-bold mb-3" style={{ color: '#000000' }}>
              {isDragActive ? 'Drop it here' : 'Upload File'}
            </h3>
            <p className="text-base font-semibold text-center" style={{ color: '#1a1a1a' }}>
              Drag and drop your .xml or .zip file here
            </p>
            <p className="text-sm font-medium mt-2" style={{ color: '#2a2a2a' }}>
              or click to browse
            </p>
          </div>
        </motion.div>
      )}

      {files.length > 0 &&
        files.map((file, idx) => (
          <motion.div
            key={"file" + idx}
            layoutId={idx === 0 ? "file-upload" : "file-upload-" + idx}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative overflow-hidden z-40 flex flex-col items-center justify-center w-full mx-auto"
            style={{
              background: 'rgba(255, 255, 255, 0.3)',
              backdropFilter: 'blur(30px)',
              WebkitBackdropFilter: 'blur(30px)',
              border: '2px solid rgba(255, 255, 255, 0.5)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
              borderRadius: '24px',
              aspectRatio: '1',
              maxWidth: '400px',
              margin: '0 auto',
              padding: '40px'
            }}
          >
            {/* File Icon */}
            <div className="mb-8 p-5 rounded-2xl" style={{
              background: 'rgba(255, 255, 255, 0.5)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
            }}>
              <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#000000" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
            </div>

            {/* File Name */}
            <motion.h3
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-xl font-bold text-center mb-6 px-4"
              style={{ 
                color: '#000000',
                wordBreak: 'break-word',
                lineHeight: '1.3'
              }}
            >
              {file.name}
            </motion.h3>

            {/* File Details */}
            <div className="flex flex-col gap-3 w-full px-2">
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-between px-5 py-3.5 rounded-xl"
                style={{ 
                  background: 'rgba(255, 255, 255, 0.5)', 
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)'
                }}
              >
                <span className="text-sm font-semibold" style={{ color: '#000000' }}>Size</span>
                <span className="text-base font-bold" style={{ color: '#000000' }}>
                  {(file.size / (1024 * 1024)).toFixed(2)} MB
                </span>
              </motion.div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.1 }}
                className="flex items-center justify-between px-5 py-3.5 rounded-xl"
                style={{ 
                  background: 'rgba(255, 255, 255, 0.5)',
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)'
                }}
              >
                <span className="text-sm font-semibold" style={{ color: '#000000' }}>Type</span>
                <span className="text-base font-bold" style={{ color: '#000000' }}>
                  {file.type || 'text/xml'}
                </span>
              </motion.div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="flex items-center justify-between px-5 py-3.5 rounded-xl"
                style={{ 
                  background: 'rgba(255, 255, 255, 0.5)',
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)',
                  border: '1px solid rgba(255, 255, 255, 0.4)'
                }}
              >
                <span className="text-sm font-semibold" style={{ color: '#000000' }}>Modified</span>
                <span className="text-sm font-bold" style={{ color: '#000000' }}>
                  {new Date(file.lastModified).toLocaleDateString()}
                </span>
              </motion.div>
            </div>
          </motion.div>
        ))}
    </div>
  );
};

export function GridPattern() {
  const columns = 41;
  const rows = 11;
  return (
    <div className="flex bg-gray-100 dark:bg-neutral-900 flex-shrink-0 flex-wrap justify-center items-center gap-x-px gap-y-px scale-105">
      {Array.from({ length: rows }).map((_, row) =>
        Array.from({ length: columns }).map((_, col) => {
          const index = row * columns + col;
          return (
            <div
              key={`${col}-${row}`}
              className={`w-10 h-10 flex flex-shrink-0 rounded-[2px] ${
                index % 2 === 0
                  ? "bg-gray-50 dark:bg-neutral-950"
                  : "bg-gray-50 dark:bg-neutral-950 shadow-[0px_0px_1px_3px_rgba(255,255,255,1)_inset] dark:shadow-[0px_0px_1px_3px_rgba(0,0,0,1)_inset]"
              }`}
            />
          );
        })
      )}
    </div>
  );
}
