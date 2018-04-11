Evil House Monitor
==================

Your house doesn't have to be evil, but if it is, then you can use this to display a *rad* summary
of what's constantly broken.

I think of this as my "fool me once" script. If something fails in one of my many home appliances,
and it could have been figured out faster by some python code, then I put that code here. 

I am hoping this is useful to someone else, and a few people asked for it, but this is far from a
complete solution. If you are looking for something more turn key, I might suggest
home-assistant.io, which has a ton of great work built into it.

I put in an example configl.yaml, which allows me some flexability, so it might for you as well, and
you run it with:

    python display.py

You'll need these dependencies:

    pip install --user paho-mqtt urwid

