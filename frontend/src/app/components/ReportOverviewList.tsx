'use client'
import styles from '@/styles/ReportOverviewList.module.css'
import ReportOverview from './ReportOverview'
import { unstable_noStore as noStore } from 'next/cache'
import { useEffect, useState } from 'react';

const apiUrl = process.env.NEXT_PUBLIC_REPORT_GENERATOR_URL;

async function fetchReports(){
  const response = await fetch(`${apiUrl}/reports`)
  if (!response.ok) {
    throw new Error('Network response was not ok');
  }
  const data = await response.json();
  return data;
}

export default function ReportOverviewList(){

  const [reportsData, setReportsData] = useState<Array<any>>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
      async function getData() {
        try{
          const result = await fetchReports();
          setReportsData(result);
        } catch (error:any) {
          console.log(error)
          setError(error.toString())
        } finally {
          setIsLoading(false)
        }
        
      }
      getData();
  }, []);
    if (isLoading){
      return (
        <div className={styles.reportsContainer}>
          Loading Reports...
        </div>
      );
    }
    if (error){
      return (
        <div>
          Something went wrong while loading!
        </div>
      )
    }
    return <div className={styles.reportsContainer}>
        {reportsData.map((item) => (
        <ReportOverview key={item.gw_id} gw_id={item.gw_id} headline={item.headline} complete={item.complete}/>
      ))}
    </div>
}