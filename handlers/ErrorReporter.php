<?php
class ErrorReporter {
    var $soapServer;
 
    function ErrorReporter () {
        error_reporting(E_ALL ^ E_NOTICE);

        $this->soapServer=new SOAP_Server;
 
        $this->soapServer->addObjectMap($this,'http://www.sabayonlinux.org#EquoError');
 
        $this->soapServer->service($GLOBALS['HTTP_RAW_POST_DATA']);
    }
 
    function sendError($error) {
	mail("sabayonlinux@sabayonlinux.org", "Entropy Error Report", $error);
        return 'ok';
    }
}
?>
