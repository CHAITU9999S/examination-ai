import { redirect } from "next/navigation";

export default function AccountSecurityRedirect() {
  redirect("/account/management");
}
