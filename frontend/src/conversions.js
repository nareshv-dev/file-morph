import { ImageIcon, MarkdownIcon, PdfIcon, WordIcon } from './components/Icons.jsx'

export const CONVERSIONS = [
  { id: 'pdf-to-docx', title: 'PDF to DOCX', description: 'Preserve each fixed PDF page visually inside a Word document.', sourceLabel: 'PDF', sourceExtensions: ['pdf'], outputLabel: 'DOCX', Icon: PdfIcon, limitation: 'Page content is image-based, so it is not fully editable or reflowable.' },
  { id: 'docx-to-pdf', title: 'DOCX to PDF', description: 'Render common Word structure, tables, links, and images into PDF.', sourceLabel: 'DOCX', sourceExtensions: ['docx'], outputLabel: 'PDF', Icon: WordIcon, limitation: 'Advanced fields, floating objects, and uncommon fonts can render differently.' },
  { id: 'to-markdown', title: 'PDF / DOCX to Markdown', description: 'Extract readable structure and embedded images into clean Markdown.', sourceLabel: 'PDF or DOCX', sourceExtensions: ['pdf', 'docx'], outputLabel: 'Markdown', Icon: MarkdownIcon, limitation: 'Downloads include Markdown and image assets in a ZIP. Fixed page geometry is not retained; scanned PDFs need OCR.' },
  ...[
    ['markdown-to-pdf', 'Markdown to PDF', ['md', 'markdown'], 'PDF', MarkdownIcon],
    ['markdown-to-docx', 'Markdown to DOCX', ['md', 'markdown'], 'DOCX', MarkdownIcon],
    ['markdown-to-html', 'Markdown to HTML', ['md', 'markdown'], 'HTML', MarkdownIcon],
    ['docx-to-html', 'DOCX to HTML', ['docx'], 'HTML', WordIcon],
    ['docx-to-text', 'DOCX to plain text', ['docx'], 'TXT', WordIcon],
    ['html-to-pdf', 'HTML to PDF', ['html', 'htm'], 'PDF', MarkdownIcon],
    ['html-to-docx', 'HTML to DOCX', ['html', 'htm'], 'DOCX', MarkdownIcon],
    ['text-to-pdf', 'TXT to PDF', ['txt'], 'PDF', MarkdownIcon],
    ['text-to-docx', 'TXT to DOCX', ['txt'], 'DOCX', MarkdownIcon],
    ['image-to-pdf', 'JPG / PNG / WebP to PDF', ['jpg', 'jpeg', 'png', 'webp'], 'PDF', ImageIcon],
    ['pdf-to-png', 'PDF pages to PNG', ['pdf'], 'PNG archive', PdfIcon],
    ['pdf-to-jpg', 'PDF pages to JPG', ['pdf'], 'JPG archive', PdfIcon],
    ['compress-pdf', 'Compress PDF', ['pdf'], 'PDF', PdfIcon],
    ['images-to-pdf', 'Multiple images to one PDF', ['jpg', 'jpeg', 'png', 'webp'], 'PDF', ImageIcon],
    ['merge-pdf', 'Merge PDF files', ['pdf'], 'PDF', PdfIcon],
    ['split-pdf', 'Split PDF by page range', ['pdf'], 'PDF', PdfIcon],
  ].map(([id, title, sourceExtensions, outputLabel, Icon]) => ({
    id, title, sourceExtensions, outputLabel, Icon,
    sourceLabel: sourceExtensions.map((extension) => extension.toUpperCase()).join(' / '),
    multiple: ['images-to-pdf', 'merge-pdf'].includes(id),
    description: ['pdf-to-png', 'pdf-to-jpg'].includes(id) ? 'Export every page as an image in a downloadable ZIP archive.' : 'Convert readable content with safe, bounded document processing.',
    limitation: id === 'compress-pdf' ? 'Already optimized PDFs may not become smaller.' : id === 'split-pdf' ? 'Select valid page numbers or ranges within the PDF.' : id === 'docx-to-html' ? 'Text, headings, and basic tables are exported; images and advanced styling are omitted.' : ['markdown-to-docx', 'html-to-docx'].includes(id) ? 'Basic headings, paragraphs, lists, and tables are preserved; images, inline styling, and complex layout are simplified or omitted.' : 'Advanced layout can differ. HTML scripts, unsafe markup, and external assets are removed; images are fixed-layout in PDF.',
  })),
]
