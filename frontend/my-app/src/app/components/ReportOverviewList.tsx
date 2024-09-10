import styles from '@/styles/ReportOverviewList.module.css'
import ReportOverview from './ReportOverview'

export default function ReportOverviewList(){
    const temp = [{gw_id: 1, headline:'Hello World'},{gw_id: 2, headline:'Hello World'},{gw_id: 3, headline:'Hello World'},{gw_id: 4, headline:'Hello World'}]
    return <div className={styles.reportsContainer}>
        {temp.map((item) => (
        <ReportOverview key={item.gw_id} gw_id={item.gw_id} headline={item.headline}/>
      ))}
    </div>
}