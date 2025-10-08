import { useState } from 'react';
import { X, ZoomIn, ZoomOut, Download } from 'lucide-react';

interface ImageData {
  id: string;
  page_number: number;
  position: { x: number; y: number; width: number; height: number };
  description?: string;
  ocr_text?: string;
  image_base64: string;
}

interface ImageViewerProps {
  images: ImageData[];
  documentTitle?: string;
}

export default function ImageViewer({ images, documentTitle }: ImageViewerProps) {
  const [selectedImage, setSelectedImage] = useState<ImageData | null>(null);
  const [zoom, setZoom] = useState(1);

  if (!images || images.length === 0) {
    return null;
  }

  const handleDownload = (image: ImageData) => {
    const link = document.createElement('a');
    link.href = `data:image/png;base64,${image.image_base64}`;
    link.download = `image_page_${image.page_number}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-2">
      {/* Image thumbnails grid */}
      <div className="grid grid-cols-2 gap-2">
        {images.map((image) => (
          <div
            key={image.id}
            className="relative group cursor-pointer rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 hover:border-blue-500 dark:hover:border-blue-400 transition-colors"
            onClick={() => setSelectedImage(image)}
          >
            <img
              src={`data:image/png;base64,${image.image_base64}`}
              alt={image.description || `Image page ${image.page_number}`}
              className="w-full h-32 object-cover"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-opacity flex items-center justify-center">
              <ZoomIn className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            {image.description && (
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black to-transparent p-2">
                <p className="text-xs text-white line-clamp-2">{image.description}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Full size modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 z-50 bg-black bg-opacity-90 flex items-center justify-center p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="relative max-w-6xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Controls */}
            <div className="absolute top-4 right-4 flex gap-2 bg-white dark:bg-gray-800 rounded-lg p-2 shadow-lg z-10">
              <button
                onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Zoom out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoom(Math.min(3, zoom + 0.25))}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Zoom in"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => handleDownload(selectedImage)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Download"
              >
                <Download className="w-4 h-4" />
              </button>
              <button
                onClick={() => setSelectedImage(null)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Image */}
            <img
              src={`data:image/png;base64,${selectedImage.image_base64}`}
              alt={selectedImage.description || `Image page ${selectedImage.page_number}`}
              className="rounded-lg shadow-2xl mx-auto"
              style={{
                transform: `scale(${zoom})`,
                transformOrigin: 'center',
                transition: 'transform 0.2s ease-out',
                maxWidth: '100%',
                height: 'auto'
              }}
            />

            {/* Image metadata */}
            {(selectedImage.description || selectedImage.ocr_text) && (
              <div className="mt-4 bg-white dark:bg-gray-800 rounded-lg p-4 shadow-lg">
                {selectedImage.description && (
                  <div className="mb-2">
                    <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                      Description :
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {selectedImage.description}
                    </p>
                  </div>
                )}
                {selectedImage.ocr_text && (
                  <div>
                    <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
                      Texte extrait :
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                      {selectedImage.ocr_text}
                    </p>
                  </div>
                )}
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
                  Page {selectedImage.page_number}
                  {documentTitle && ` • ${documentTitle}`}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
