import PageHeader from '../components/PageHeader'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'

const sections = {
  reports: {
    icon: 'report',
    title: 'Reports are not available yet',
    description: 'Monthly summaries and charts will be built from confirmed transactions only.',
  },
  settings: {
    icon: 'settings',
    title: 'More settings are on the way',
    description: 'Appearance and your workspace label are already available from the sidebar and top bar.',
  },
}

export default function SectionPage({ destination }) {
  const section = sections[destination.id] ?? {
    icon: destination.icon,
    title: 'This section is not available yet',
    description: 'Confirmed financial activity will appear here once it is implemented.',
  }

  return <>
    <PageHeader eyebrow={destination.label} title={destination.heading} description={destination.description} />
    <Card className="section-card">
      <EmptyState icon={section.icon} title={section.title} description={section.description} />
    </Card>
  </>
}