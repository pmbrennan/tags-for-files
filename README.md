# tags-for-files
Rudimentary tagging system for managing media files.

At the moment, this is configured to be a command-line Python script. You can run it in the same directory
where your media files are stored, accompanied by a file called `tags.txt`.
You run it by invoking the command:

    python -i TagsForFiles.py

and then you can manage your files via the included functions.

A proper UI is forthcoming.

**TODO**: Add a real UI to this project.

**TODO**: Add a comprehensive test suite.

## Text file format

Data format is as follows:
A record consists of a sequence of non-blank lines.
 - The first line contains the file path
 - An optional number of lines after the path contains file comments,
   indicated by the presence of a '#' as the first character of the line.
 - Every subsequent non-blank line contains tags, each separated by 1 or more spaces.
 - A tag in the form '<k>=<v>' where k and v are both valid strings is considered
   to be a variable, with the name `k` and the value `v`. All variables are simple 
   strings.
 - Complete records are separated by one or more blank lines.

Example:

    J:\Music\BitterSweet\Drama\01-01- Intro Dramatico.mp3
    album=drama artist=bitter:sweet bitter-sweet title=intro-dramatico year=2008
    
    J:\Music\BitterSweet\Drama\01-02- Get What I Want.mp3
    album=drama artist=bitter:sweet 
    bitter-sweet title=get-what-i-want year=2008
    
    J:\Music\BitterSweet\Drama\01-03- Come Along With Me.mp3
    album=drama artist=bitter:sweet bitter-sweet title=come-along-with-me year=2008
    
    J:\Music\BitterSweet\Drama\01-04- The Bomb.mp3
    # 'The Bomb' by Bitter:Sweet
    album=drama artist=bitter:sweet bitter-sweet title=the-bomb year=2008
    
    J:\Music\BitterSweet\Drama\01-05- Drama.mp3
    album=drama artist=bitter:sweet bitter-sweet title=drama year=2008

