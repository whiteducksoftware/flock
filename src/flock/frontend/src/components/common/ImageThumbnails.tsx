import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { fetchArtifact } from '../../services/api';
import { valueAtPath, type ImageSummary } from '../../utils/imageFields';
import styles from './ImageThumbnails.module.css';

interface ImageThumbnailsProps {
  artifactId: string;
  images: ImageSummary[];
}

interface OpenImage {
  path: string;
  url?: string;
  error?: string;
}

const sizeLabel = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

/**
 * Previews of an artifact's images (#512). The dashboard receives small thumbnails;
 * the full image is loaded only when one is opened, through the artifact endpoint,
 * which applies the artifact's visibility.
 */
const ImageThumbnails: React.FC<ImageThumbnailsProps> = ({ artifactId, images }) => {
  const [open, setOpen] = useState<OpenImage | null>(null);

  const openImage = async (path: string) => {
    setOpen({ path });
    try {
      const artifact = await fetchArtifact(artifactId);
      const url = valueAtPath(artifact.payload, path)?.url;
      if (typeof url !== 'string' || !url.startsWith('data:image/')) {
        throw new Error('no image at this path');
      }
      setOpen((current) => (current?.path === path ? { path, url } : current));
    } catch {
      setOpen((current) =>
        current?.path === path
          ? { path, error: 'Could not load the full image (it may be gone or not visible to you).' }
          : current
      );
    }
  };

  if (images.length === 0) return null;

  return (
    <>
      <div className={styles.thumbnails}>
        {images.map((image) => (
          <figure key={image.path} className={styles.thumbnail}>
            <button
              type="button"
              className={styles.thumbnailButton}
              onClick={() => void openImage(image.path)}
              aria-label={`Open ${image.path}`}
              title="Open the full image"
            >
              <img src={image.thumb} alt={image.path} />
            </button>
            <figcaption className={styles.caption}>
              {image.path} · {image.mime} · {sizeLabel(image.bytes)}
            </figcaption>
          </figure>
        ))}
      </div>
      {/* In document.body: detail windows are transformed, which would confine a fixed overlay */}
      {open && createPortal(
        <div className={styles.overlay} role="dialog" aria-label={`${open.path} full size`}>
          <div className={styles.dialog}>
            <div className={styles.dialogHeader}>
              <span>{open.path}</span>
              <button type="button" onClick={() => setOpen(null)} aria-label="Close" className={styles.close}>
                ×
              </button>
            </div>
            {open.url && <img src={open.url} alt={`${open.path} (full size)`} className={styles.full} />}
            {open.error && <p className={styles.message}>{open.error}</p>}
            {!open.url && !open.error && <p className={styles.message}>Loading…</p>}
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

export default ImageThumbnails;
