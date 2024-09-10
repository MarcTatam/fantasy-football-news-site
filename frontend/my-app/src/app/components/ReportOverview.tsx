'use client'
import styles from '@/styles/ReportOverview.module.css'

import { useRouter } from 'next/navigation';

interface ReportProps {
    gw_id:Number
    headline:string
}

export default function ReportOverview(reportProps:ReportProps){
    const router = useRouter();

    const handleClick = () => {
        router.push('/report/'+reportProps.gw_id.toString())
    }
    return (<div className={styles.container} onClick={handleClick}>
        <div className={styles.weekContainer}>
            <p className={styles.containerBody}>Week {reportProps.gw_id.toString()}</p>
        </div>
        <div className={styles.headingContainter}>
            <h2 className={styles.containerHeading}>{reportProps.headline}</h2>
        </div>
    </div>)
}