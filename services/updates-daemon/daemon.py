
import gobject
import dbus
import dbus.service
import dbus.mainloop.glib



# Entropy imports
from entropy.misc import TimeScheduled, ParallelTask
from entropy.i18n import _
from entropy.exceptions import *
import entropy.tools as entropyTools
from entropy.client.interfaces import Client as EquoInterface
from entropy.client.interfaces import Repository as RepoInterface
from entropy.transceivers import urlFetcher
from entropy.const import etpConst

class Entropy(EquoInterface):

   #TODO check if it's needed
   def init_singleton(self):
       EquoInterface.init_singleton(self, noclientdb = True)
       self.connect_progress_objects()
       self.nocolor()

   #TODO we have to choose what to do: send things over dbus?
   def connect_progress_objects(self):
       #self.progress_tooltip = self.update_tooltip
       self.updateProgress = self.updateProgress
       self.progress_tooltip_message_title = _("Updates Daemon")
       self.progress = self.printText

   #FIXME placeholder: see above
   def updateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):
      count_str = ""
      if count:
         if percent:
            count_str = str(int(round((float(count[0])/count[1])*100,1)))+"% "
         else:
            count_str = "(%s/%s) " % (str(count[0]),str(count[1]),)

         message = count_str+_(text)
        #if importance in (1,2):
         if importance == 2:
            print  message
         else:
            self.printText(message)

   #FIXME only for debug at the moment
   def printText(self, string = ""):
      print "print text " + string

        
class equo_daemon(dbus.service.Object):
    def __init__(self,  conn,  object_path = "/org/sabayon/entropy/equo_daemon"):
        dbus.service.Object.__init__ ( self, conn, object_path )
        self.Entropy = Entropy()
        self.debug = True
        self.last_error = None
        self.error_threshold = 0
        self.last_error_is_network_error = None
        self.last_error_is_exception = None

        self.repositories_to_update = None
        self.rc = None

        self.available_packages = None
        self.alert_msg = []

    # Send signal if we have something to comunicate    
    @dbus.service.signal(dbus_interface='it.itsme.backend', signature='')        
    def new_alert(self):
       pass

    # Add things to the alert buffer
    def add_alert(self, string, msg, urgency = "critical"):
       if self.debug: print "alert : " + string + " " + msg
       self.alert_msg.append(msg)
       self.new_alert
    
    # Call this method for update the repositories
    @dbus.service.method ( "org.sabayon.entropy", in_signature='', out_signature='s')
    def update_db(self):
       #FIXME we have to decide how we comunicate errors
       rc = 0
       repositories_to_update, rc = self.compare_repositories_status()

       if repositories_to_update and rc == 0:
          repos = repositories_to_update.keys()
          
          if self.debug: print "run_refresh: loading repository interface"
          try:
             repoConn = self.Entropy.Repositories(repos, fetchSecurity = False, noEquoCheck = True)
             if self.debug: print "run_refresh: repository interface loaded"
          except MissingParameter, e:
             self.last_error = "%s: %s" % (_("No repositories specified in"),etpConst['repositoriesconf'],)
             self.error_threshold += 1
             if self.debug: print "run_refresh: MissingParameter exception, error: %s" % (e,)
          except OnlineMirrorError, e:
             self.last_error = _("Repository Network Error")
             self.last_error_is_network_error = 1
             if self.debug: print "run_refresh: OnlineMirrorError exception, error: %s" % (e,)
          except Exception, e:
             self.error_threshold += 1
             self.last_error_is_exception = 1
             self.last_error = "%s: %s" % (_('Unhandled exception'),e,)
             if self.debug: print "run_refresh: Unhandled exception, error: %s" % (e,)
          else:
             # -128: sync error, something bad happened
             # -2: repositories not available (all)
             # -1: not able to update all the repositories
             if self.debug: print "run_refresh: preparing to run sync"
             rc = repoConn.sync()
             rc = rc*-1
             del repoConn
             if self.debug: print "run_refresh: sync done"

          if self.debug: print "run_refresh: sync closed, rc: %s" % (rc,)

       if rc == 1:
          err = _("No repositories specified. Cannot check for package updates.")
          self.add_alert( _("Updates: attention"), err )
          self.error_threshold += 1
          self.last_error = err
       elif rc == 2:
          err = _("Cannot connect to the Updates Service, you're probably not connected to the world.")
          self.add_alert( _("Updates: connection issues"), err )
          self.last_error_is_network_error = 1
          self.last_error = err
       elif rc == -1:
          err = _("Not all the repositories have been fetched for checking")
          self.add_alert( _("Updates: repository issues"), err )
          self.last_error_is_network_error = 1
          self.last_error = err
       elif rc == -2:
          err = _("No repositories found online")
          self.add_alert( _("Updates: repository issues"), err )
          self.last_error_is_network_error = 1
          self.last_error = err
       elif rc == -128:
          err = _("Synchronization errors. Cannot update repositories. Check logs.")
          self.add_alert( _("Updates: sync issues"), err )
          self.error_threshold += 1
          self.last_error = err
       elif isinstance(rc,basestring):
          self.add_alert( _("Updates: unhandled error"), rc )
          self.error_threshold += 1
          self.last_error_is_exception = 1
          self.last_error = rc
          
          if self.last_error_is_network_error:
             #self.update_tooltip(_("Updates: connection issues"))
             #FIXME choose if we have to return something... i don't think so
             return "Error"

       try:
          update, remove, fine = self.Entropy.calculate_world_updates()
          del fine, remove
       except Exception, e:
          msg = "%s: %s" % (_("Updates: error"),e,)
          self.add_alert(_("Updates: error"), msg)
          self.error_threshold += 1
          self.last_error_is_exception = 1
          self.last_error = str(e)

       if self.last_error:
          msg = "%s: %s" % (_("Updates issue:"),self.last_error,)
            #self.update_tooltip(msg)
          return "Error"
       if rc == 0:
            #self.update_tooltip(old_tip)
          pass
       if update:
          self.available_packages = update[:]
          msg = "%s %d %s" % (_("There are"),len(update),_("updates available."),)
          #self.update_tooltip(msg)
          self.add_alert(    _("Updates available"),
                              msg,
                              urgency = 'critical'
                              )
          self.updates_available()
       else:
          #self.update_tooltip(_("So far, so good. w00t!"))
          self.add_alert(    _("Everything up-to-date"),
                              _("So far, so good. w00t!"),
                              urgency = 'low'
                              )

       return "Updated"

    # return a list that contains all updates available
    @dbus.service.method ( "org.sabayon.entropy", in_signature='', out_signature='v')
    def get_available_updates(self):
        if not self.available_packages:
           print "azz"
           return ["No updates available",]

        names = {}
        entropy_data = {}

        available_updates = []
        
        for pkg in self.available_packages:
            dbconn = self.Entropy.open_repository(pkg[1])
            atom = dbconn.retrieveAtom(pkg[0])
            avail = dbconn.retrieveVersion(pkg[0])
            avail_rev = dbconn.retrieveRevision(pkg[0])
            key, slot = dbconn.retrieveKeySlot(pkg[0])
            installed_match = self.Entropy.clientDbconn.atomMatch(key, matchSlot = slot)

            if installed_match[0] != -1:
                installed = self.Entropy.clientDbconn.retrieveVersion(installed_match[0])
                installed_rev = self.Entropy.clientDbconn.retrieveRevision(installed_match[0])
            else:
                installed = _("Not installed")
            if key == "sys-apps/entropy":
                entropy_data['avail'] = avail+"~"+str(avail_rev)[:]
                entropy_data['installed'] = installed+"~"+str(installed_rev)

            names[atom] = {}
            names[atom]['installed'] = installed+"~"+str(installed_rev)
            names[atom]['avail'] = avail+"~"+str(avail_rev)


        ordered_names = names.keys()
        ordered_names.sort()
        for name in ordered_names:
           available_updates.append([name, names[name]['installed'], names[name]['avail']])

        critical_text = []
        if entropy_data.has_key("avail"):
            msg = "%s sys-apps/entropy <b>%s</b> %s, %s <b>%s</b>. %s." % (
                    _("Your system currently has"),
                    entropy_data['installed'],
                    _("installed"),
                    _("but the latest available version is"),
                    entropy_data['avail'],
                    _("It is recommended that you upgrade to the latest before updating any other packages")
            )
            critical_text.append(msg)

        if critical_text:
            if self.old_critical_text != critical_text:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 1)
            else:
                self.notice_window.set_critical('<br><br>'.join(critical_text), critical_active = 0)
            self.old_critical_text = critical_text
        else:
           print critical_text
        if len(available_updates)==0:
           available_updates.append("No updates available")
        print available_updates
        return available_updates

    # compare repos status for updates
    @dbus.service.method ( "org.sabayon.entropy", in_signature='', out_signature='')    
    def compare_repositories_status(self, send_singal = True):
        repos = {}
        
        try:
            repoConn = self.Entropy.Repositories(noEquoCheck = True, fetchSecurity = False)
        except MissingParameter:
            print "1"
            return repos,1 # no repositories specified
        except OnlineMirrorError:
            print "2"
            return repos,2 # not connected ??
        except Exception, e:
            print "3"
            return repos,str(e) # unknown error
        
        # now get remote
        for repoid in self.Entropy.SystemSettings['repositories']['available']:
            print repoid
            if repoConn.is_repository_updatable(repoid):
                self.Entropy.repository_move_clear_cache(repoid)
                repos[repoid] = {}
                repos[repoid]['local_revision'] = self.Entropy.get_repository_revision(repoid)
                repos[repoid]['remote_revision'] = repoConn.get_online_repository_revision(repoid)
                
        del repoConn
        print "all done"
        if send_singal: # FIXME add check before send signale for beeing sure that there's really updates
           self.some_repo_has_update()
        return repos, 0
    
    # signal that tell if some repos has update available
    @dbus.service.signal(dbus_interface='it.itsme.backend', signature='')
    def some_repo_has_update(self):
       pass

    # signal sent when updates are available for retrive
    @dbus.service.signal(dbus_interface='it.itsme.backend', signature='')
    def updates_available(self):
       pass
