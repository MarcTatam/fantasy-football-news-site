'use client'
import styles from "@/styles/Button.module.css"
import { useRouter } from 'next/navigation';

interface ButtonProps{
    linkAddress:string;
    text:string
}

export default function Button(props:ButtonProps){
    const router = useRouter();
    const handleClick = () => {
        router.push(props.linkAddress)
    }
    return (<div className={styles.container} onClick={handleClick}>
        <p>{props.text}</p>
        <p>{">"}</p>
    </div>)
}