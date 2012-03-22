<?php

# Get variables
$reservationid = $_GET["reservationid"];
$indexid = $_GET["indexid"];
$internalip = $_GET["internalip"];
$externaldns = $_GET["externaldns"];
$second_seed_index = $_GET["second_seed_index"];
$third_seed_index = $_GET["third_seed_index"];

$dbname='db-dsec';
$seedtable ="seeds";
$statstable ="stats";

try {
  $db = new PDO("sqlite:" . $dbname);
} catch(PDOException $e) {
  echo $e->getMessage();
}


function setupDB(){
  global $db, $seedtable, $statstable;
  
  # Create a table. Only the first request is actually executed.
  $stmt = "CREATE TABLE $seedtable(
              seed_id VARCHAR(22) NOT NULL PRIMARY KEY,
              reservation_id VARCHAR(20) NOT NULL,
              index_id INTEGER NOT NULL,
              seed_ip VARCHAR(70) NOT NULL,
              seed_dns VARCHAR(70) NOT NULL,
              created_at TIMESTAMP NOT NULL
              )";
  $db->exec($stmt);
  $stmt = "CREATE TABLE $statstable(
              reservation_id VARCHAR(20) NOT NULL PRIMARY KEY,
              num_dcs INTEGER NOT NULL,
              cluster_size INTEGER NOT NULL,
              created_at TIMESTAMP NOT NULL
              )";
  $db->exec($stmt);
  
  # Remove records older than 5 minutes.
  $stmt = "DELETE FROM $seedtable
              WHERE $seedtable.created_at < strftime('%s','now') - 600;";
  $db->exec($stmt);  
}

function populateSeedList(){
  global $db, $seedtable, $statstable;
  global $reservationid, $indexid, $internalip, $externaldns;
  
  # Populate the seed variable for this reservation_id. Only the first request is actually executed.
  $stmt = $db->prepare("INSERT INTO $seedtable(seed_id, reservation_id, index_id, seed_ip, seed_dns, created_at) 
                        VALUES (:seedid, :reservationid, :indexid, :internalip, :externaldns, strftime('%s','now'))");
  $seedid = $reservationid . $indexid;
  $stmt->bindParam(':seedid', $seedid, PDO::PARAM_STR, 22);
  $stmt->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $stmt->bindParam(':indexid', $indexid, PDO::PARAM_STR, 3);
  $stmt->bindParam(':internalip', $internalip, PDO::PARAM_STR, 70);
  $stmt->bindParam(':externaldns', $externaldns, PDO::PARAM_STR, 70);
  
  if ($stmt->execute())
    $i = 0;

  # Return the currently set seed
  returnSeed();
}

function returnSeed(){
  global $db, $seedtable;
  global $reservationid, $externaldns, $second_seed_index, $third_seed_index, $indexid;
  
  # Find external dns of first node
  $query = $db->prepare("SELECT seed_dns
                         FROM $seedtable 
                         WHERE reservation_id=:reservationid AND index_id=0");
  $query->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $query->execute();
  $results = $query->fetchAll();
  $zeronodedns = $results[0]['seed_dns'];

  # Query for the seeds.
  $query = $db->prepare("SELECT seed_ip, index_id 
                         FROM $seedtable 
                         WHERE reservation_id=:reservationid AND (index_id=0 OR index_id=:second_seed_index OR index_id=:third_seed_index)
                         ORDER BY index_id");
  $query->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $query->bindParam(':second_seed_index', $second_seed_index, PDO::PARAM_STR, 20);
  $query->bindParam(':third_seed_index', $third_seed_index, PDO::PARAM_STR, 20);
  $query->execute();
  $results = $query->fetchAll();

  # Stats Tracking
  if ($indexid == 0 and sizeof($results) >= 1){
    newStats(1);
  } elseif ($indexid > 0){
    updateStats();
  }

  #print_r($results);

  $seed_list = array();
  foreach ($results as $result){
    array_push($seed_list, $result['seed_ip']);
  }

  $data = array('number_of_returned_ips' => sizeof($results), 'opscenter_dns' => $externaldns, 'seeds' => $seed_list);
  echo json_encode($data);
}

# Simple stat collectors. Isn't designed to be fool proof, just highly confidential.
# If two clusters start up within the same time period, stats may be uneven.

# Only called on new clusters
function newStats($initialSize){
  global $db, $statstable, $second_seed_index, $third_seed_index, $reservationid;

  $numDCS = 1;
  if (intval($second_seed_index) > 0){
    $numDCS++;
  }
  if (intval($third_seed_index) > intval($second_seed_index)){
    $numDCS++;
  }

  $query = $db->prepare("INSERT INTO $statstable(reservation_id, cluster_size, num_dcs, created_at) 
                         VALUES (:reservationid, $initialSize, $numDCS, strftime('%s','now'))");
  $query->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $query->execute();
}

# Only called when finding an existing seed
function updateStats(){
  global $db, $statstable, $reservationid, $indexid;
  $query = $db->prepare("SELECT cluster_size
                         FROM $statstable 
                         WHERE reservation_id=:reservationid");
  $query->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $query->execute();
  $results = $query->fetchAll();
  
  $newValue = max($results[0]['cluster_size'], intval($indexid) + 1);
  $query = $db->prepare("UPDATE $statstable
                         SET cluster_size=$newValue
                         WHERE reservation_id=:reservationid");
  $query->bindParam(':reservationid', $reservationid, PDO::PARAM_STR, 20);
  $query->execute();
}


setupDB();
populateSeedList();
?>
