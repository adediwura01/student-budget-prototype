export default function PageHeader({ eyebrow, title, description, children }) {
  return <div className="page-header">
    <div><p className="page-eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>
    {children && <div className="page-header-actions">{children}</div>}
  </div>
}
