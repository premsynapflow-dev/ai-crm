def generate_auto_reply(summary: str, ticket_id: str):

    return f"""
Hello,

Thanks for contacting us.

Your request has been received and our team will review it shortly.

Ticket ID: {ticket_id}

Summary:
{summary}

Please include this Ticket ID in future replies.

Regards,
Support Team
"""
