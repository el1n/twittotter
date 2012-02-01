-- phpMyAdmin SQL Dump
-- version 2.11.11.3
-- http://www.phpmyadmin.net
--
-- Host: localhost
-- Generation Time: Jan 28, 2012 at 01:58 AM
-- Server version: 5.1.52
-- PHP Version: 5.3.3

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `twittotter`
--

-- --------------------------------------------------------

--
-- Table structure for table `Bind`
--

CREATE TABLE IF NOT EXISTS `Bind` (
  `status_id` bigint(20) unsigned NOT NULL,
  `referring_user_id` bigint(20) unsigned DEFAULT NULL,
  `referring_screen_name` varchar(16) DEFAULT NULL,
  `referred_user_id` bigint(20) unsigned DEFAULT NULL,
  `referred_screen_name` varchar(16) DEFAULT NULL,
  `flag` bigint(20) unsigned NOT NULL DEFAULT '0',
  KEY `referring_user_id` (`referring_user_id`,`referring_screen_name`),
  KEY `referred_user_id` (`referred_user_id`,`referred_screen_name`),
  KEY `status_id` (`status_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `Queue`
--

CREATE TABLE IF NOT EXISTS `Queue` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) unsigned NOT NULL,
  `screen_name` varchar(16) DEFAULT NULL,
  `order` varchar(255) DEFAULT NULL,
  `flag` bigint(20) unsigned NOT NULL DEFAULT '1',
  `priority` tinyint(4) NOT NULL DEFAULT '1',
  `atime` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `mtime` timestamp NOT NULL DEFAULT '0000-00-00 00:00:00',
  `ctime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `revision` int(11) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`,`flag`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8 AUTO_INCREMENT=117 ;

-- --------------------------------------------------------

--
-- Table structure for table `Token`
--

CREATE TABLE IF NOT EXISTS `Token` (
  `user_id` bigint(20) unsigned NOT NULL,
  `screen_name` varchar(16) DEFAULT NULL,
  `ACCESS_TOKEN` varchar(255) DEFAULT NULL,
  `ACCESS_TOKEN_SECRET` varchar(255) DEFAULT NULL,
  `ctime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `revision` int(11) NOT NULL DEFAULT '1',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `screen_name` (`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- --------------------------------------------------------

--
-- Table structure for table `Tweet`
--

CREATE TABLE IF NOT EXISTS `Tweet` (
  `status_id` bigint(20) unsigned NOT NULL,
  `user_id` bigint(20) unsigned NOT NULL,
  `screen_name` varchar(16) DEFAULT NULL,
  `text` varchar(255) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `structure` mediumblob,
  `flag` bigint(20) unsigned NOT NULL DEFAULT '0',
  `revision` int(11) NOT NULL DEFAULT '1',
  PRIMARY KEY (`status_id`),
  KEY `screen_name` (`user_id`,`screen_name`,`created_at`,`flag`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
