const iconProps = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

export function UploadIcon({ size = 28 }) {
  return <svg {...iconProps} width={size} height={size}><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"/><path d="M5 14v4.5A1.5 1.5 0 006.5 20h11a1.5 1.5 0 001.5-1.5V14"/></svg>
}
export function FileIcon() { return <svg {...iconProps}><path d="M6 2.5h8l4 4V21H6z"/><path d="M14 2.5v4h4M9 12h6M9 16h6"/></svg> }
export function ShieldIcon() { return <svg {...iconProps}><path d="M12 21s7-3.5 7-9.5V5l-7-2.5L5 5v6.5C5 17.5 12 21 12 21z"/><path d="M9.5 12l1.5 1.5 3.5-4"/></svg> }
export function CheckIcon() { return <svg {...iconProps}><path d="M20 6L9 17l-5-5"/></svg> }
export function CloseIcon() { return <svg {...iconProps}><path d="M18 6L6 18M6 6l12 12"/></svg> }
export function DownloadIcon() { return <svg {...iconProps}><path d="M12 3v12m0 0l4-4m-4 4l-4-4"/><path d="M5 20h14"/></svg> }
export function RefreshIcon() { return <svg {...iconProps}><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 8A7 7 0 0118.7 7M5.3 17A7 7 0 0017.9 16"/></svg> }
export function ImageIcon() { return <svg {...iconProps}><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="M21 15l-5-5L5 20"/></svg> }
