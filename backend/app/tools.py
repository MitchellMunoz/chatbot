TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Check whether a specific room type is available at a hotel for a given date range for a customer. Use this before calling get_quote. Anytime a customer asks for availability to stay at one of our two hotels, you must first use this tool to check the database to see if there is any space."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hotel": {
                    "type": "string",
                    "enum": ["antigua", "pacifico"],
                    "description": "which hotel to check.",
                },
                "room": {
                    "type": "string",
                    "description": "The type of room at the hotel.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check-in date for the hotel stay.",
                },
                "check_out": {
                    "type": "string",
                    "description": "The check-out date for the hotel stay.",
                },
            },
            "required": ["hotel", "room", "check_in", "check_out"],
        },
    },
    {
        "name": ""
    }
    {
        "name": "get_quote",
        "description": "Calculate the hotel quote based on the users requests and the information in the MYSQL database. You will multiply the dollar value by 7.5 to get the value in quetzales.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hotel": {"type": "string", "description": "The name of the hotel."},
                "room": {
                    "type": "string",
                    "description": "The type of room at the hotel.",
                },
                "check_in": {
                    "type": "string",
                    "description": "The check-in date for the hotel stay.",
                },
                "check_out": {
                    "type": "string",
                    "description": "The check-out date for the hotel stay.",
                },
            },
            "required": ["hotel", "room", "check_in", "check_out"],
        },
    },
]



