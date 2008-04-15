<?php

function insert_attachment($data,$boundary,$filename) {

    $mymessage = "--".$boundary."\n";
    $mymessage .= "Content-Type: application/octet-stream; name=\"".$filename."\"\n";
    $mymessage .= "Content-Transfer-Encoding: base64\n";
    //$mymessage .= "Content-Disposition: attachment\n";
    $mymessage .= chunk_split(base64_encode($data));
    $mymessage .= "\n\n";
    $mymessage .= "--".$boundary."--\n";
    return $mymessage;

}

$arch = $_POST['arch'];
$ip = $_SERVER['REMOTE_ADDR'];
$version = $_POST['version'];
$system_version = $_POST['system_version'];
$name = $_POST['name'];
$email = $_POST['email'];
$description = $_POST['description'];
$mail = "lxnay@sabayonlinux.org";
$subject = "Entropy Error Reporting Handler";
$random_hash = md5(date('r', time()));

$headers = "MIME-Version: 1.0\n";
$boundary = "PHP-mixed-".$random_hash;
$headers .= "Content-Type: multipart/mixed; boundary=\"".$boundary."\"\n";
if ($email) {
    $headers .= "From: ".$email."\nReply-To: ".$email."\n\n";
} else {
    $headers .= "From: www-data@sabayonlinux.org\nReply-To: www-data@sabayonlinux.org\n\n";
}

$message = "--".$boundary."\n";
$message .= "Content-Type: text/plain; charset=\"iso-8859-1\"\n";
$message .= "Content-Transfer-Encoding: 7bit\n";

$message .= "Hello, this is an Entropy error report.\n";
$message .= $_POST['stacktrace'];
$message .= "\n\n";
$message .= "Architecture: " . $arch . "\n";
$message .= "Arguments: " . $_POST['arguments'] . "\n";
$message .= "UID: " . $_POST['uid'] . "\n";
$message .= 'Name: ' . $name . "\n";
$message .= 'E-mail: ' . $email . "\n";
$message .= 'Description: ' . $description . "\n";
$message .= 'Version: ' . $version . "\n";
$message .= 'System Version: ' . $system_version . "\n";
$message .= 'IP: ' . $ip . "\n";
$message .= 'Date: ' . date("G:i d/F/Y") . "\n";
$message .= "--\n";

$message .= insert_attachment($_POST['errordata'],$boundary,'errordata.txt');
$message .= insert_attachment($_POST['processes'],$boundary,'processes.txt');
$message .= insert_attachment($_POST['lspci'],$boundary,'lspci.txt');
$message .= insert_attachment($_POST['dmesg'],$boundary,'dmesg.txt');


if ($_POST['stacktrace'] && $_POST['arch'] && $ip) {
        $rc = mail($mail, $subject, $message, $headers);
        print_r($rc);
}
?>