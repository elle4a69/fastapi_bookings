import { useEffect, useState } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { Badge } from "../../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { apiClient } from "../../../lib/api";
import { Mail, MessageSquare } from "lucide-react";

interface NotificationMessage {
  id: string;
  recipient: string;
  type: "EMAIL" | "SMS";
  subject?: string;
  bodyPreview: string;
  dateSent: string;
  status: "SENT" | "FAILED" | "PENDING";
}

export default function MessagesPage() {
  const [messages, setMessages] = useState<NotificationMessage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const data = await apiClient.get<NotificationMessage[]>("/api/admin/notifications/messages");
        setMessages(data);
      } catch (error) {
        console.error("Failed to fetch messages", error);
      } finally {
        setLoading(false);
      }
    };
    fetchMessages();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Messages</h1>
        <p className="text-muted-foreground">View all sent notification messages.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Message Log</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Recipient</TableHead>
                <TableHead>Content Preview</TableHead>
                <TableHead>Date Sent</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8">Loading...</TableCell>
                </TableRow>
              ) : messages.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8">No messages found.</TableCell>
                </TableRow>
              ) : (
                messages.map((msg) => (
                  <TableRow key={msg.id}>
                    <TableCell>
                      {msg.type === "EMAIL" ? <Mail className="w-4 h-4" /> : <MessageSquare className="w-4 h-4" />}
                    </TableCell>
                    <TableCell>{msg.recipient}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        {msg.subject && <span className="font-medium text-sm">{msg.subject}</span>}
                        <span className="text-xs text-muted-foreground truncate max-w-[200px]">{msg.bodyPreview}</span>
                      </div>
                    </TableCell>
                    <TableCell>{new Date(msg.dateSent).toLocaleString()}</TableCell>
                    <TableCell>
                      <Badge variant={msg.status === "SENT" ? "default" : msg.status === "FAILED" ? "destructive" : "secondary"}>
                        {msg.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
