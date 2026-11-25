"use client";
import { useParams } from "next/navigation";
import ExamStudentRoster from "../../../shared/ExamStudentRoster";
export default function AdminExamStudentsPage(){
 const params=useParams<{examId:string}>();
 return <ExamStudentRoster examId={String(params.examId||"")} readOnly={true}/>;
}
