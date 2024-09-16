'use client'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useState, useEffect } from 'react';
import styles from '@/styles/Graph.module.css'

const apiUrl = process.env.NEXT_PUBLIC_REPORT_GENERATOR_URL;

interface TeamData {
    teamName: string;
    dataPoints: Array<number>
}

interface ChartDataPoint {
    name: string;
    [key: string]: string | number; // Allow any string key with string or number value
  }


function flattenData(fetchedData:Array<TeamData>){
    const numberOfWeeks = fetchedData[0].dataPoints.length;
    const transformedData:ChartDataPoint[] = [];

    for (let week = 0; week < numberOfWeeks; week++) {
      const weekData:ChartDataPoint = {
        name: `Week ${week + 1}`,
      };

      fetchedData.forEach(team => {
        weekData[team.teamName] = team.dataPoints[week];
      });

      transformedData.push(weekData);
    }

    return transformedData;
}

function generateLines(fetchedData:Array<TeamData>){
    let colours = ['#484A47', '#5C6D70', '#A37774', '#E88873','#E0AC9D']
    const lines = []
    for (let i = 0; i < fetchedData.length; i++){
        lines.push(<Line type="monotone" dataKey={fetchedData[i].teamName} stroke={colours[i]} key={i.toString()} dot={false}/>)
    }
    return lines
}

export default function LeagueGraph(){
    const [TeamsData, setTeamsData] = useState<Array<TeamData>>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    useEffect(() => {
        const fetchTeamHistory = async () => {
            try {
                const response = await fetch(`${apiUrl}/teams/history`);
                if (!response.ok) {
                    throw new Error('Failed to fetch teams history');
                }
                const data:Array<any> = await response.json();
                let out:Array<TeamData> = []
                for(let i=0;i<data.length;i ++){
                    let item = data[i]
                    out.push({teamName : item.team_name, dataPoints:item.points_history})
                }
                setTeamsData(out)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'An error occurred');
            } finally {
                setIsLoading(false);
            }
          };
          fetchTeamHistory();
    },[])
    if (isLoading){
        return(<div className={styles.graphContainer} style={{justifyContent:"center", alignItems:"center", display:'flex'}}>
            Loading...
        </div>)
    }
    if (error){
        return(<div className={styles.graphContainer}>
            {error}
        </div>)
    }
    const transformedData = flattenData(TeamsData);
    const lines = generateLines(TeamsData);
    return (
        <div className={styles.graphContainer}>
            <ResponsiveContainer height={400}>
                <LineChart data={transformedData} margin={{ top: 20, right: 40, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend margin={{ top: 0, left: 0, right: 0, bottom: 0 }} iconType='plainline'/>
                    {lines}
                </LineChart>
            </ResponsiveContainer>
        </div>
    )
}