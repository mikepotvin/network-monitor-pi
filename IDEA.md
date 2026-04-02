Goal: Use Raspberry Pi 3 to monitor my network for packet loss, disconnects, and other issues. I want to be able to view 
the data using a web interface that I can access from any device on my network.

Key Features:
- I want to know when my network was down and for how long.
- I want to know if there's any packet loss.
- I want this to be passive and not take up much bandwidth
- I want to be able to easily view when the network was down
- I want to know what kind of errors are causing the network to be down
- For example, when on my windows machine I run `ping www.google.ca -t` there's messages returned when there's an error, I like those messages.
- I would also like for you to research and come up with other network stats that might be useful.
- I want the technology for this to be free, I have the raspberry pi.
- I want the code base for this to be on my github
- The rasberry pi is HEADLESS so it doesn't have a monitor. I will need to be able to remote into it, please also handle that.
- I want this to always be running, if the PI restarts for some reason, this should auto load and not require any manual input.
- I would prefer a PRD with tasks that can be completed as we go.
- I want to plan this all as much as we can upfront and then execute the individual tasks with sub agents to use less tokens.