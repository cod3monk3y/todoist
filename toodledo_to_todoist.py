#!/usr/bin/env python
from bs4 import BeautifulSoup
import re
import sys
import codecs

# filter out any items that aren't in a folder that starts with this string
FOLDER_FILTER = None #'EXPORTTEST'
TODOIST_TASK_LIMIT = 120
INCLUDE_COMPLETED = False

class Folder:
    def __init__(self,name):
        
        # remove any bad characters from the name
        
        self.name = re.sub('[/]','_',name)
        
        self.tasks = {}  # dictionary by ID
        
class Task:
    def __init__(self,id,title):
        self.title = title
        self.id = id
        self.children = [] # array of child tasks
        self.parent = None # link back to the parent
        self.folder = None
        self.folderMismatch = False
        self.dueDate = None
        self.completedDate = None
        self.tags = [] # any tags on the object
        self.note = None
        self.repeat = None
        
    def count(self):
        n = 1 # self
        if self.children != None:
            n += sum( [c.count() for c in self.children])
        return n
        
    def isComplete(self):
        return self.completedDate != None
    
    def checkFolderMismatch(self):
        if self.parent and (self.parent.folder != self.folder):
            self.folderMismatch = True

    # task can only have one parent
    def setParent(self,parent):
        self.parent = parent
        parent.children.append(self)
        
        self.checkFolderMismatch()
        
    # task can only be in one folder
    def setFolder(self,folder):
        self.folder = folder
        folder.tasks[self.id] = self
        
        self.checkFolderMismatch()

class TextExport:
    def __init__(self, toodledo):
        self.folders = toodledo.folders.values()
        self.outFile = None
        
    def printTask(self, indent, task, folder):
        
        # detect folder errors.. don't show tasks in folders that are different from their parent
        # tasks
        mismatch = task.folderMismatch
            
        tag = ''
        if mismatch:
            tag = "@import_mismatched_folders"
    
        self.outFile.write( indent + ' '.join((task.id, task.title, '(', task.folder.name, ')', tag)))
        if task.isComplete():
            self.outFile.write('completed=' + task.completedDate)
        if task.tags != None:
            self.outFile.write(' ' + ','.join(task.tags))
        if task.repeat != None:
            self.outFile.write(' repeat:' + task.repeat)
            
        if task.note != None:
            self.outFile.write('\nNOTE:' + task.note)
            
        self.outFile.write('\n')
        
        indent = '   ' + indent 
        for child in task.children:
            self.printTask(indent,child,folder)
        
    def export(self):
        
        self.outFile = codecs.open('__text_tasks.txt','w+','utf-8')
        
        print 'all folders...'
        for folder in self.folders:
            self.outFile.write( folder.name + '\n' )
            
            indent = '   '
            for (task_id, task) in folder.tasks.iteritems():
                
                #if task.folderMismatch:
                #    self.outFile.write( indent + ' '.join(('folder mismatch', task.id, task.title, '(', task.folder.name, ')', '\n')))
                #    continue
                
                # only print top level items. parented items will be nested
                if task.parent == None:
                    self.printTask(indent, task,folder)
                
        self.outFile.close()
        self.outFile = None
        
class TodoistExport:
    def __init__(self,toodledo):
        self.folders = toodledo.folders.values()
        self.count = 0
        
        # todoist has a max of 120 items per project
        self.TASK_LIMIT = TODOIST_TASK_LIMIT
    
    def export(self):
        for folder in self.folders:
            
            self.count = 0
            
            filename = '__' + folder.name + '[00000].txt'
            f = codecs.open(filename, 'w+', 'utf-8')
            
            # track the number of tasks so that the files can be split automatically
            n = 0
            fileCount = 1
            
            # only print top level items. parented items will be nested
            for task in folder.tasks.itervalues():
                if task.parent == None:
                    
                    nextCount = task.count()
                    if(nextCount + n > self.TASK_LIMIT):
                        # SPLIT THE FILE
                        n = 0
                        print "Warning: splitting tasks %s" % (folder.name)
                        f.close
                        fileCount += 1
                        filename = '__%s__part_%d_[00000].txt' % (folder.name, fileCount)
                        f = codecs.open(filename, 'w+', 'utf-8')
                    
                    self.exportTask(f, '', task)
                    
                    n += nextCount
            
            if self.count > self.TASK_LIMIT:
                print "Error: project has more than %d items: %s (%d)" % (self.TASK_LIMIT, folder.name, self.count)
            
            f.close()
            f = None
            
    def exportTask(self,f,indent,task):
        
        
        s = "%s%s" % (indent,task.title)
        if task.folderMismatch:
            s += " @__import_folder_mismatch"
            
        if task.isComplete():
            s += " @__import_completed"
            
        # repeated tasks will be processed manually
        if task.repeat != None:
            s += " @__import_repeat"
            
        if task.tags != None:
            s += ''.join([" @"+tag for tag in task.tags])
            
        if task.dueDate != None:
            s += " [[date %s]]" % task.dueDate
        
        s += '\n'
        
        if task.note != None:
            # TODOIST multi-line notes are separated by tabs, not newlines
            s += '[[NOTE]]: ' + re.sub('[\r\n]+','\t', task.note)
            s += '\n'
            
        if task.repeat != None:
            s += '[[NOTE]]: repeat -- ' + task.repeat + '\n'
            
        if task.folderMismatch:
            s += '[[NOTE]]: folder -- ' + task.folder.name + '\n'
        
        f.write( s )
        self.count += 1
        
        indent = indent + '...'
        for child in task.children:
            self.exportTask(f,indent,child)
                    
def get(s):
    if s == None:
        return None
    if s.string == None or s.string.strip() == '':
        return None
    return s.string.strip()

# NOTE: in Toodoist export, sub-tasks that have different folders
# from parent tasks will be tagged with @import_mismatched_folders
class Toodledo:
    def __init__(self):
        self.folders = {}
        self.tasks = {} # all tasks by ID

        
    def parseXML(self,filename):
        print 'opening file:', filename
        f = open(filename,'r')
        xml = file.read(f)
        
        print  'cooking soup...'
        soup = BeautifulSoup(xml)
        
        # HACK: test only the export test folder
        if FOLDER_FILTER != None:
            
            for item in soup.find_all('item'):
                folder = get(item.folder)
                if folder == None or not folder.startswith(FOLDER_FILTER):
                    item.decompose()
            
            outf = open('_filtered_soup.xml', 'w=')
            outf.write( soup.prettify() )
            outf.close()

        print 'parsing...'
        for item in soup.find_all('item'):

            # get the folder name, or replace with NOFOLDER for
            # items that have no folder
            folderName = "NOFOLDER"
            if None != get(item.folder):
                folderName = get(item.folder)

            # HACK temporary filter by filter
            if FOLDER_FILTER != None:
                if not folderName.startswith(FOLDER_FILTER):
                    continue

            # create the task
            task = Task(get(item.id), get(item.title))

            # skip completed items
            # was this task completed?
            completedDate = get(item.completed)
            if completedDate != None and completedDate != '0000-00-00':
                task.completedDate = completedDate
                
                # option to skip completed items
                if INCLUDE_COMPLETED == False:
                    continue
                
            # find or create the folder this item belongs in
            folder = None
            if not folderName in self.folders:
                #print "Adding folder: ", s
                self.folders[folderName] = folder = Folder(folderName)
            else:
                folder = self.folders[folderName]

            task.setFolder(folder)
            
            # find the parent and create the tree hierarchy
            parent_id = get(item.find('parent'))# using .parent would give us the BeautifulSoup XML tag parent
            parent = None
            if parent_id in self.tasks:
                parent = self.tasks[parent_id]
            
            if parent != None:
                task.setParent(parent)
                
            # is there a due date?
            task.dueDate = get(item.duedate)
            
            # is there a note?
            task.note = get(item.note)
            
            # is there some repeat text?
            rp = get(item.repeat)
            if rp != None and rp != 'None':
                task.repeat = rp
            
            # are there any tags
            stag = get(item.tag)
            if stag != None:
                task.tags = [x.strip() for x in stag.split(',')]
                        
            # cache tasks for parenting, as the tasks themselves may be in different folders
            # from the parent task... which is bizarre but allows things like "Waiting"
            # and "Next" to be folders (instead they should be tags!)
            self.tasks[task.id] = task

if len(sys.argv) < 2:
    print ''
    print '    Usage: python toodledo_to_todoist.py <xml_filename>'
    print ''
    exit(1)

filename = sys.argv[1]

# import the Toodledo backup XML file
toodledo = Toodledo()
toodledo.parseXML(filename)

# export to a text file
print "exporting text..."
textexport = TextExport(toodledo)
textexport.export()
        
# export for Todoist
print "exporting todoist..."
todoist = TodoistExport(toodledo)
todoist.export()
