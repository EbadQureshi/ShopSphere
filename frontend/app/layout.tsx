import "./globals.css"; import Header from "@/components/Header"; import ChatWidget from "@/components/ChatWidget"; import {NotificationsProvider} from "@/components/Notifications";
export const metadata={title:"ShopSphere",description:"Modern online shopping store"};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><NotificationsProvider><Header/>{children}<footer className="mt-20 border-t bg-white p-10 text-center text-sm text-gray-500">© 2026 ShopSphere</footer><ChatWidget/></NotificationsProvider></body></html>}
